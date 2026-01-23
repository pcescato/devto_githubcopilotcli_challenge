# Architecture Migration Guide

## From SQLite Synchronous to PostgreSQL Async

This document explains the architectural refactoring from the original SQLite-based synchronous implementation to the modern PostgreSQL-first async architecture.

## Overview

### Old Architecture (devto_tracker.py + core/database.py)

```
┌─────────────────┐
│  devto_tracker  │
│    (Sync)       │
└────────┬────────┘
         │
         ├─► requests.get()      ──► DEV.to API
         │
         └─► sqlite3.connect()   ──► devto_metrics.db
                │
                └─► DatabaseManager
                       └─► row_factory = sqlite3.Row
```

**Characteristics:**
- Synchronous blocking I/O
- `requests` library for HTTP
- Direct `sqlite3` connections
- Raw SQL strings with SQLite functions
- `INSERT OR IGNORE/REPLACE` patterns
- JSON stored as TEXT strings
- Manual connection management

### New Architecture (app/services/*)

```
┌───────────────────────┐
│   DevToService        │
│   (Async)             │
└──────────┬────────────┘
           │
           ├─► httpx.AsyncClient()   ──► DEV.to API
           │        └─► Non-blocking async requests
           │
           └─► AsyncEngine           ──► PostgreSQL 18
                    │
                    ├─► Connection pooling (20 base + 10 overflow)
                    ├─► AsyncConnection with context manager
                    └─► Result.mappings() for dict-like rows
                             │
                             └─► SQLAlchemy Core Tables
                                      └─► Type-safe queries

┌───────────────────────┐
│  AnalyticsService     │
│   (Async)             │
└──────────┬────────────┘
           │
           └─► AsyncEngine           ──► PostgreSQL 18
                    │
                    └─► select() queries with PostgreSQL functions
                             └─► interval math, date ranges, aggregations
```

**Characteristics:**
- Async/await throughout
- `httpx.AsyncClient` for HTTP
- SQLAlchemy Core with `AsyncEngine`
- Type-safe query builders
- PostgreSQL-specific `ON CONFLICT` clauses
- JSONB native storage
- ARRAY types for lists
- Automatic connection pooling

## Key Migrations

### 1. HTTP Requests

**Before (requests - blocking):**
```python
import requests

response = requests.get(
    "https://dev.to/api/articles/me/all",
    headers={"api-key": api_key},
    params={"per_page": 1000}
)
articles = response.json()
```

**After (httpx - async):**
```python
import httpx

async with httpx.AsyncClient(headers={"api-key": api_key}) as client:
    response = await client.get(
        "https://dev.to/api/articles/me/all",
        params={"per_page": 1000}
    )
    articles = response.json()
```

### 2. Database Connections

**Before (sqlite3):**
```python
import sqlite3

conn = sqlite3.connect("devto_metrics.db")
conn.row_factory = sqlite3.Row  # Dict-like access

cursor = conn.execute("SELECT * FROM articles WHERE id = ?", (123,))
row = cursor.fetchone()
print(row['title'])  # Dict-like access

conn.commit()
conn.close()
```

**After (SQLAlchemy async):**
```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@host/db",
    pool_size=20,
    pool_pre_ping=True,
)

async with engine.begin() as conn:
    query = select(articles).where(articles.c.id == 123)
    result = await conn.execute(query)
    row = result.mappings().first()  # Dict-like access
    print(row['title'])
```

### 3. INSERT Patterns

**Before (SQLite OR IGNORE):**
```python
conn.execute("""
    INSERT OR IGNORE INTO comments 
    (comment_id, article_id, body, created_at)
    VALUES (?, ?, ?, ?)
""", (comment_id, article_id, body, created_at))
```

**After (PostgreSQL ON CONFLICT):**
```python
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(comments).values(
    comment_id=comment_id,
    article_id=article_id,
    body=body,
    created_at=created_at,
)

stmt = stmt.on_conflict_do_nothing(constraint='uq_comments_comment_id')
await conn.execute(stmt)
```

### 4. UPSERT Patterns

**Before (SQLite OR REPLACE):**
```python
conn.execute("""
    INSERT OR REPLACE INTO daily_analytics
    (article_id, date, page_views, reactions_total)
    VALUES (?, ?, ?, ?)
""", (article_id, date, views, reactions))
```

**After (PostgreSQL ON CONFLICT DO UPDATE):**
```python
stmt = pg_insert(daily_analytics).values(
    article_id=article_id,
    date=date,
    page_views=views,
    reactions_total=reactions,
)

stmt = stmt.on_conflict_do_update(
    constraint='uq_daily_analytics_article_date',
    set_={
        'page_views': stmt.excluded.page_views,
        'reactions_total': stmt.excluded.reactions_total,
    }
)
await conn.execute(stmt)
```

### 5. Date Math

**Before (SQLite julianday):**
```python
query = """
    SELECT 
        title,
        julianday('now') - julianday(published_at) as age_days
    FROM articles
    WHERE published_at < date('now', '-30 days')
"""
```

**After (PostgreSQL intervals):**
```python
from sqlalchemy import func, text

query = select(
    articles.c.title,
    (func.extract('epoch', func.now() - articles.c.published_at) / 86400).label('age_days')
).where(
    articles.c.published_at < func.current_date() - text("INTERVAL '30 days'")
)
```

### 6. Tag Storage

**Before (SQLite TEXT):**
```python
# Store tags as JSON string
tags_json = json.dumps(['python', 'sql'])
conn.execute(
    "INSERT INTO articles (tags) VALUES (?)",
    (tags_json,)
)

# Retrieve and parse
row = conn.execute("SELECT tags FROM articles").fetchone()
tags = json.loads(row['tags'])
```

**After (PostgreSQL ARRAY + JSONB):**
```python
# Store as both JSONB and ARRAY
tags_json = json.dumps(['python', 'sql'])  # For JSONB column
tag_list = ['python', 'sql']                # For ARRAY column

stmt = insert(articles).values(
    tags=tags_json,      # JSONB type (flexible metadata)
    tag_list=tag_list,   # ARRAY(String) type (simple queries)
)
await conn.execute(stmt)

# Query is simpler
query = select(articles).where(
    articles.c.tag_list.contains(['python'])  # Native array containment
)
```

### 7. Rate Limiting

**Before (time.sleep - blocking):**
```python
import time

for article in articles:
    process_article(article)
    time.sleep(0.5)  # Blocks entire thread
```

**After (asyncio.sleep - non-blocking):**
```python
import asyncio

for article in articles:
    await process_article(article)
    await asyncio.sleep(0.5)  # Only blocks this coroutine
```

### 8. Timezone Handling

**Before (naive datetimes):**
```python
from datetime import datetime

timestamp = datetime.now().isoformat()  # Potentially naive
conn.execute(
    "INSERT INTO events (occurred_at) VALUES (?)",
    (timestamp,)
)
```

**After (timezone-aware UTC):**
```python
from datetime import datetime, timezone

timestamp = datetime.now(timezone.utc)  # Always aware

stmt = insert(events).values(occurred_at=timestamp)
await conn.execute(stmt)
```

## Quality Score Formula (Preserved)

The quality score calculation is preserved exactly:

```python
# Formula: (completion × 0.7) + (min(engagement, 20) × 1.5)

def calculate_quality_score(article):
    # Completion percentage
    length_sec = article['reading_time_minutes'] * 60
    avg_read = article['avg_read_seconds']
    completion = min(100, (avg_read / length_sec) * 100) if length_sec > 0 else 0
    
    # Engagement percentage (90-day window)
    views = article['views_90d']
    reactions = article['reactions_90d']
    comments = article['comments_90d']
    engagement = ((reactions + comments) / views) * 100
    
    # Quality score: 70% completion, 30% engagement (capped at 20%)
    score = (completion * 0.7) + (min(engagement, 20) * 1.5)
    
    return score
```

## Business Logic Preserved

All business logic patterns are maintained:

1. **Follower Delta**: `new_followers = current_count - last_count`
2. **7-day Attribution Window**: 6-hour tolerance for correlating article views to new followers
3. **Incremental Processing**: LEFT JOIN ... WHERE right.id IS NULL pattern
4. **INSERT Idempotency**: ON CONFLICT DO NOTHING for comments, snapshots
5. **UPDATE on Conflict**: ON CONFLICT DO UPDATE for daily_analytics, referrers
6. **90-day Window**: Historical analytics limited to last 90 days
7. **Reaction Gap Analysis**: Lifetime vs breakdown sum shows removed reactions
8. **Long-tail Champions**: Articles >30 days old with consistent traffic

## Performance Improvements

### Connection Pooling
```python
# Before: New connection per request
conn = sqlite3.connect("db.sqlite")
# ... use connection ...
conn.close()

# After: Pool of 20 + 10 overflow connections
engine = create_async_engine(url, pool_size=20, max_overflow=10)
# Connections are reused automatically
```

### Concurrent Operations
```python
# Before: Sequential blocking operations
for article in articles:
    fetch_comments(article)      # Blocks for HTTP
    save_to_database(comments)   # Blocks for I/O

# After: Concurrent async operations
tasks = [fetch_and_save(article) for article in articles]
await asyncio.gather(*tasks)  # All run concurrently
```

### Prepared Statements
```python
# Before: SQL parsed every time
for i in range(1000):
    conn.execute("INSERT INTO ... VALUES (?, ?)", (i, data))

# After: Compiled once, reused
stmt = insert(table).values(...)  # Compiled to SQL once
for i in range(1000):
    await conn.execute(stmt, {'id': i, 'data': data})
```

## Migration Checklist

- [x] Replace `requests` with `httpx.AsyncClient`
- [x] Replace `sqlite3` with SQLAlchemy + asyncpg
- [x] Convert all functions to `async def`
- [x] Replace `time.sleep()` with `await asyncio.sleep()`
- [x] Convert `INSERT OR IGNORE` to `ON CONFLICT DO NOTHING`
- [x] Convert `INSERT OR REPLACE` to `ON CONFLICT DO UPDATE`
- [x] Replace `julianday()` with PostgreSQL interval math
- [x] Replace `date('now', '-N days')` with `CURRENT_DATE - INTERVAL 'N days'`
- [x] Ensure all timestamps are timezone-aware UTC
- [x] Add tag/tag_list conversion for ARRAY types
- [x] Preserve all business logic formulas
- [x] Maintain 90-day analytics window
- [x] Keep follower delta calculation
- [x] Document all changes

## Running the New Services

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DEVTO_API_KEY="your_api_key"
export POSTGRES_USER="devto"
export POSTGRES_PASSWORD="your_password"
export POSTGRES_HOST="localhost"
export POSTGRES_PORT="5432"
export POSTGRES_DB="devto_analytics"
```

### DevToService
```bash
# Sync all data
python -m app.services.devto_service --all

# Or use in code
python -c "
import asyncio
from app.services import create_service

async def main():
    async with await create_service() as service:
        await service.sync_all()

asyncio.run(main())
"
```

### AnalyticsService
```bash
# Show quality dashboard
python -m app.services.analytics_service

# Show article breakdown
python -m app.services.analytics_service --article=123456
```

## Testing

```bash
# Validate syntax
python3 -c "
import ast
for module in ['devto_service', 'analytics_service']:
    with open(f'app/services/{module}.py') as f:
        ast.parse(f.read())
    print(f'✅ {module}.py is valid')
"

# Test imports
python3 -c "
from app.services import DevToService, AnalyticsService
print('✅ Services import successfully')
"

# Test database connection (async)
python3 -c "
import asyncio
from app.services import create_service

async def test():
    service = await create_service()
    print('✅ Service created successfully')

asyncio.run(test())
"
```

## Troubleshooting

### asyncpg not installed
```bash
pip install asyncpg
```

### httpx not installed
```bash
pip install httpx
```

### "RuntimeError: Service not initialized"
Make sure to use the async context manager:
```python
async with await create_service() as service:
    await service.sync_all()
```

### "Missing required environment variables"
Ensure all PostgreSQL credentials are set:
```bash
export POSTGRES_USER="devto"
export POSTGRES_PASSWORD="password"
```

### Connection pool exhausted
Increase pool size:
```python
service = DevToService(
    api_key=api_key,
    db_url="postgresql+asyncpg://..."
)
# Edit __init__ to change pool_size parameter
```

## Future Enhancements

- [ ] FastAPI REST API endpoints
- [ ] Celery tasks for scheduled collection
- [ ] Valkey/Redis caching layer
- [ ] GraphQL API for flexible queries
- [ ] Websocket support for real-time updates
- [ ] Prometheus metrics export
- [ ] Distributed tracing with OpenTelemetry
- [ ] Content tracker integration
- [ ] Follower attribution analytics
- [ ] A/B testing framework
