# DEV.to Analytics Services

Modern async PostgreSQL-first architecture for DEV.to data collection and analysis.

## Services

### DevToService

Handles all DEV.to API interactions and data synchronization to PostgreSQL.

**Features:**
- Async API calls using `httpx.AsyncClient`
- PostgreSQL insert patterns (`ON CONFLICT DO NOTHING/UPDATE`)
- Automatic tag/tag_list conversion for ARRAY types
- Rate limiting with configurable delays
- Timezone-aware UTC timestamps

**Usage:**

```python
import asyncio
from app.services import create_service

async def main():
    # Create service from environment variables
    async with await create_service() as service:
        # Sync everything
        summary = await service.sync_all()
        print(summary)
        
        # Or sync individually
        await service.sync_articles()
        await service.sync_followers()
        await service.sync_comments()
        await service.sync_rich_analytics()

asyncio.run(main())
```

**CLI Usage:**

```bash
# Sync all data
python -m app.services.devto_service --all

# Sync specific data types
python -m app.services.devto_service --articles
python -m app.services.devto_service --followers
python -m app.services.devto_service --comments
python -m app.services.devto_service --rich
```

### AnalyticsService

Provides quality metrics and traffic analysis using SQLAlchemy Core queries.

**Features:**
- PostgreSQL-native date/time functions (replaces SQLite julianday)
- Async query execution
- Quality score calculation: `(completion × 0.7) + (min(engagement, 20) × 1.5)`
- 90-day analytics windows
- Long-tail champion detection

**Usage:**

```python
import asyncio
from app.services import create_analytics_service

async def main():
    service = await create_analytics_service()
    
    # Get quality dashboard
    dashboard = await service.get_quality_dashboard()
    
    # Or get individual metrics
    read_time = await service.get_read_time_analysis(limit=10)
    reactions = await service.get_reaction_breakdown(limit=10)
    quality = await service.get_quality_scores(limit=10)
    champions = await service.get_long_tail_champions(limit=10)
    
    # Get article daily breakdown
    breakdown = await service.get_article_daily_breakdown(article_id=123456)

asyncio.run(main())
```

**CLI Usage:**

```bash
# Show full dashboard
python -m app.services.analytics_service
python -m app.services.analytics_service --overview

# Refresh article stats cache (quality scores + follower attribution)
python -m app.services.analytics_service --refresh

# Show specific article breakdown
python -m app.services.analytics_service --article=123456
```

**Key Methods:**

- `refresh_all_stats()` - Calculate and cache quality scores and follower attribution
  - Quality Score: `(completion × 0.7) + (min(engagement, 20) × 1.5)`
  - 7-day and 30-day follower attribution (Share of Voice)
  - UPSERT to `article_stats_cache` table
  
- `get_quality_scores()` - Article quality metrics with completion and engagement rates
- `get_reaction_breakdown()` - Lifetime vs 90-day reaction analysis (identifies gaps)
- `weighted_follower_attribution()` - Proportional follower gain attribution by article
- `article_follower_correlation()` - 7-day window attribution with proximity search
- `engagement_evolution()` - Velocity analysis (views/hour) around milestone events
- `get_overview()` - Global trends with delta vs previous period
- `best_publishing_times()` - Optimal day/hour analysis for publishing

### NLPService

High-performance sentiment analysis and spam detection using VADER and spaCy.

**Features:**
- Pre-loaded spaCy and VADER models (loaded once at initialization)
- CPU-bound tasks wrapped in `asyncio.to_thread()` for async compatibility
- Exact sentiment thresholds: >=0.3 positive, <=-0.2 negative
- Spam detection with keywords and emoji patterns
- BeautifulSoup HTML cleaning (strips `<code>` and `<pre>`)
- Batch processing (50 comments per batch)
- Incremental processing with LEFT JOIN pattern
- `ON CONFLICT DO UPDATE` for idempotency

**Usage:**

```python
import asyncio
from app.services import create_nlp_service

async def main():
    service = await create_nlp_service(author_username='your_username')
    
    # Run complete analysis
    results = await service.run_analysis()
    service.print_results(results)
    
    # Or individual operations
    stats = await service.get_sentiment_stats()
    questions = await service.find_unanswered_questions()
    
    # Process specific number of comments
    results = await service.process_pending_comments(limit=100)

asyncio.run(main())
```

**CLI Usage:**

```bash
# Analyze all pending comments
python -m app.services.nlp_service

# Analyze up to 100 comments
python -m app.services.nlp_service --limit=100
```

**Sentiment Thresholds (STRICT):**
- Score >= 0.3: 🌟 Positif (Positive)
- Score <= -0.2: 😟 Négatif (Negative)
- Otherwise: 😐 Neutre (Neutral)

**Spam Detection:**
- Keywords: investigator, hack, whatsapp, kasino, slot, 777, putar, kaya
- Emojis: 🎡 🎰 💰
- Gmail phishing: @ + .com + gmail

**Prerequisites:**
```bash
# Install spaCy model
python3 -m spacy download en_core_web_sm
```

## Architecture

### Migration from SQLite to PostgreSQL

**Old Architecture:**
- Synchronous `requests` library
- Direct `sqlite3` connections
- Raw SQL strings with `julianday()`
- `INSERT OR IGNORE/REPLACE` patterns

**New Architecture:**
- Async `httpx.AsyncClient`
- SQLAlchemy Core with `AsyncEngine`
- Type-safe query builders
- PostgreSQL-specific `ON CONFLICT` clauses
- Proper interval/date math

### Key Conversions

**Date Math:**
```python
# SQLite
julianday('now') - julianday(published_at)

# PostgreSQL
EXTRACT(EPOCH FROM NOW() - published_at) / 86400
```

**Date Ranges:**
```python
# SQLite
date('now', '-30 days')

# PostgreSQL
CURRENT_DATE - INTERVAL '30 days'
```

**Upsert Patterns:**
```python
# SQLite
INSERT OR IGNORE INTO ...
INSERT OR REPLACE INTO ...

# PostgreSQL (SQLAlchemy)
from sqlalchemy.dialects.postgresql import insert as pg_insert

stmt = pg_insert(table).values(...)
stmt = stmt.on_conflict_do_nothing(constraint='uq_constraint')
# or
stmt = stmt.on_conflict_do_update(constraint='uq_constraint', set_={...})
```

## Dependencies

```bash
pip install httpx asyncpg sqlalchemy[asyncio] pgvector python-dotenv
```

## Environment Variables

Required:
- `DEVTO_API_KEY` - Your DEV.to API key
- `POSTGRES_HOST` - PostgreSQL host (default: localhost)
- `POSTGRES_PORT` - PostgreSQL port (default: 5432)
- `POSTGRES_DB` - Database name (default: devto_analytics)
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password

## Business Logic Preserved

All business logic from the original SQLite implementation is preserved:

1. **Follower Delta Calculation**: New followers = current count - last count
2. **7-day Attribution Window**: 6-hour tolerance for follower attribution
3. **Quality Score Formula**: `(completion × 0.7) + (LEAST(engagement, 20) × 1.5)`
4. **90-day Analytics Window**: Historical data and reaction breakdown limited to 90 days
5. **INSERT Idempotency**: `ON CONFLICT DO NOTHING` for comments, snapshots
6. **UPDATE on Conflict**: `ON CONFLICT DO UPDATE` for daily_analytics, referrers
7. **Tag Conversion**: JSON strings → Python lists for PostgreSQL ARRAY type
8. **Timezone Handling**: All timestamps converted to UTC-aware datetimes

## Performance

- **Connection Pooling**: 20 base connections, 10 overflow
- **Async I/O**: Non-blocking API calls and database operations
- **Batch Operations**: All inserts use bulk patterns
- **Rate Limiting**: Configurable delays between API calls (default: 0.5s)
- **Prepared Statements**: SQLAlchemy Core compiles queries once

## Error Handling

- API errors are raised via `response.raise_for_status()`
- Database errors propagate as SQLAlchemy exceptions
- Context managers ensure proper cleanup
- Rate limiting prevents API throttling

## Testing

```python
import asyncio
from app.services import create_service, create_analytics_service

async def test_collection():
    async with await create_service() as service:
        articles = await service.fetch_articles()
        assert len(articles) > 0
        
        followers = await service.fetch_followers()
        assert len(followers) >= 0

async def test_analytics():
    service = await create_analytics_service()
    scores = await service.get_quality_scores(limit=5)
    assert len(scores) <= 5

asyncio.run(test_collection())
asyncio.run(test_analytics())
```

## Future Enhancements

- [ ] Content tracker integration (article history, milestone events)
- [ ] Webhook support for real-time updates
- [ ] Caching layer with Valkey/Redis
- [ ] GraphQL API for frontend
- [ ] Celery tasks for scheduled collection
- [ ] Metrics export (Prometheus)
- [ ] Dashboard API endpoints (FastAPI)
