# SQLite to PostgreSQL Migration Guide

## Overview

This guide covers migrating your historical DEV.to analytics data from SQLite (`devto_metrics.db`) to the production PostgreSQL database.

## Prerequisites

✅ **Completed:**
- PostgreSQL database `devto_analytics` created
- Schema initialized via `app/init_database.py`
- All services running (FastAPI, Streamlit, Superset)

✅ **Required:**
- SQLite database file: `devto_metrics.db`
- Python 3.11+ with all dependencies installed
- Access to production Docker containers

## Migration Script Features

The migration script (`app/migrate_from_sqlite.py`) provides:

- ✅ **Async PostgreSQL** operations for high performance
- ✅ **Progress bars** with Rich console output
- ✅ **Batch processing** (default: 1000 records per batch)
- ✅ **Error handling** with detailed logging
- ✅ **Dry-run mode** for validation without changes
- ✅ **Resume capability** from checkpoints
- ✅ **Conflict resolution** (INSERT ON CONFLICT DO NOTHING)
- ✅ **Data validation** after migration
- ✅ **Type conversion** (JSON, dates, arrays)

## Quick Start

### 1. Copy SQLite Database to Server

```bash
# From your local machine
scp devto_metrics.db root@your-vps:/root/docker/devto_stats/
```

### 2. Dry Run (Recommended First Step)

Test the migration without making changes:

```bash
cd /root/docker
docker exec -it devto_fastapi python -m app.migrate_from_sqlite --dry-run --verbose
```

This will:
- Read all data from SQLite
- Validate data formats
- Show what would be migrated
- Report any errors without inserting data

### 3. Run Full Migration

```bash
cd /root/docker
docker exec -it devto_fastapi python -m app.migrate_from_sqlite \
    --sqlite-path devto_metrics.db \
    --verbose
```

**Estimated Time:** 30-60 seconds for ~7,000 records

### 4. Verify Migration

```bash
# Check record counts
docker exec -it devto_fastapi python << 'EOF'
import asyncio
from sqlalchemy import select, func, text
from app.db.connection import get_async_engine
from app.db.tables import *

async def verify():
    engine = get_async_engine()
    async with engine.begin() as conn:
        tables = [
            ('snapshots', snapshots),
            ('article_metrics', article_metrics),
            ('daily_analytics', daily_analytics),
            ('comments', comments),
            ('article_content', article_content),
        ]
        
        for name, table in tables:
            result = await conn.execute(select(func.count()).select_from(table))
            count = result.scalar()
            print(f"{name:20} {count:>6} rows")

asyncio.run(verify())
EOF
```

## Command Line Options

### Basic Usage

```bash
# Minimal (uses defaults)
python -m app.migrate_from_sqlite

# With SQLite path
python -m app.migrate_from_sqlite --sqlite-path /path/to/devto_metrics.db

# Dry run
python -m app.migrate_from_sqlite --dry-run

# Verbose output
python -m app.migrate_from_sqlite --verbose
```

### Advanced Options

```bash
# Migrate specific tables only
python -m app.migrate_from_sqlite --tables snapshots,article_metrics,comments

# Resume from checkpoint (if interrupted)
python -m app.migrate_from_sqlite --resume

# Custom batch size (default: 1000)
python -m app.migrate_from_sqlite --batch-size 500

# Combine options
python -m app.migrate_from_sqlite \
    --sqlite-path devto_metrics.db \
    --tables daily_analytics,referrers \
    --batch-size 2000 \
    --verbose
```

## Table Migration Order

The script migrates tables in this order (respects dependencies):

1. **snapshots** - Global account metrics
2. **article_metrics** - Article performance snapshots
3. **follower_events** - Follower count tracking
4. **followers** - Individual follower records
5. **comments** - Comment data
6. **daily_analytics** - Daily breakdown (last 90 days)
7. **referrers** - Traffic sources
8. **article_content** - Full article markdown
9. **article_code_blocks** - Code snippets
10. **article_links** - Extracted links
11. **article_history** - Change events
12. **milestone_events** - Achievement tracking
13. **comment_insights** - Sentiment analysis

## Data Transformations

### Date/Time Conversion

SQLite stores dates as TEXT, PostgreSQL uses TIMESTAMP WITH TIME ZONE:

```python
# SQLite: "2026-01-31T08:00:00Z"
# PostgreSQL: 2026-01-31 08:00:00+00:00
```

The script automatically:
- Parses ISO 8601 format
- Adds UTC timezone if missing
- Handles timezone-aware dates

### JSON Conversion

SQLite TEXT → PostgreSQL JSONB:

```python
# SQLite tags: '["python", "devops"]'
# PostgreSQL tag_list: {python, devops}  (ARRAY)
# PostgreSQL tags: {"python", "devops"}  (JSONB)
```

### Boolean Conversion

SQLite INTEGER (0/1) → PostgreSQL BOOLEAN:

```python
# SQLite is_deleted: 0
# PostgreSQL is_deleted: false
```

## Error Handling

### Common Issues

#### 1. NULL Date Values

**Error:** `Cannot parse NULL datetime`

**Cause:** Some SQLite records have NULL dates

**Resolution:** Script automatically handles NULLs, logging warnings

#### 2. JSON Parse Errors

**Error:** `Invalid JSON in tags field`

**Cause:** Malformed JSON in SQLite TEXT field

**Resolution:** Script returns NULL and logs warning

#### 3. Duplicate Keys

**Error:** `Unique constraint violation`

**Cause:** Record already exists in PostgreSQL

**Resolution:** Uses `ON CONFLICT DO NOTHING` - silently skips

#### 4. Type Mismatch

**Error:** `Cannot convert TEXT to INTEGER`

**Cause:** Data type incompatibility

**Resolution:** Script applies type conversions automatically

### Viewing Errors

All errors are logged to `migration.log`:

```bash
# View all errors
grep ERROR migration.log

# View warnings
grep WARN migration.log

# Tail live during migration
tail -f migration.log
```

## Resume Capability

If migration is interrupted, resume from last checkpoint:

```bash
# Original migration (interrupted at daily_analytics)
python -m app.migrate_from_sqlite --verbose
# ... Ctrl+C ...

# Resume from checkpoint
python -m app.migrate_from_sqlite --resume
```

Checkpoint saved to: `migration_checkpoint.json`

```json
{
  "last_completed": "comments",
  "timestamp": "2026-01-31T08:30:00",
  "stats": {
    "snapshots": {"total": 71, "inserted": 71, "errors": 0},
    "article_metrics": {"total": 3324, "inserted": 3324, "errors": 0},
    "comments": {"total": 120, "inserted": 120, "errors": 0}
  }
}
```

## Validation

After migration, the script automatically validates:

### 1. Record Counts

Compares SQLite totals vs PostgreSQL inserted counts:

```
Table                Status  PostgreSQL  Expected
───────────────────────────────────────────────────
snapshots            ✓       71          71
article_metrics      ✓       3324        3324
daily_analytics      ✓       2292        2292
comments             ✓       120         120
```

### 2. Data Integrity

Run manual checks:

```sql
-- Check for orphan records
SELECT COUNT(*) 
FROM devto_analytics.daily_analytics da
LEFT JOIN devto_analytics.article_metrics am 
  ON da.article_id = am.article_id
WHERE am.article_id IS NULL;
-- Expected: 0

-- Verify sentiment scores in valid range
SELECT MIN(sentiment_score), MAX(sentiment_score) 
FROM devto_analytics.comment_insights;
-- Expected: -1.0 to 1.0

-- Check for NULL critical fields
SELECT COUNT(*) FROM devto_analytics.article_metrics WHERE title IS NULL;
SELECT COUNT(*) FROM devto_analytics.comments WHERE body_html IS NULL;
```

### 3. Sample Data Verification

```sql
-- Compare a specific article
SELECT article_id, title, views, reactions 
FROM devto_analytics.article_metrics 
WHERE article_id = 123456 
ORDER BY collected_at DESC 
LIMIT 5;
```

Then check same article in SQLite:

```bash
sqlite3 devto_metrics.db "SELECT article_id, title, views, reactions FROM article_metrics WHERE article_id = 123456 ORDER BY collected_at DESC LIMIT 5;"
```

## Performance Tuning

### Batch Size

Default: 1000 records per batch

```bash
# Smaller batches (slower, more memory-efficient)
python -m app.migrate_from_sqlite --batch-size 500

# Larger batches (faster, more memory)
python -m app.migrate_from_sqlite --batch-size 5000
```

**Recommendations:**
- Large VPS (4GB+ RAM): 2000-5000
- Medium VPS (2GB RAM): 1000 (default)
- Small VPS (<2GB RAM): 500

### Parallel Migrations

For very large datasets, migrate tables in parallel:

```bash
# Terminal 1: Migrate snapshots and metrics
python -m app.migrate_from_sqlite --tables snapshots,article_metrics

# Terminal 2: Migrate analytics
python -m app.migrate_from_sqlite --tables daily_analytics,referrers

# Terminal 3: Migrate content
python -m app.migrate_from_sqlite --tables article_content,article_code_blocks
```

⚠️ **Note:** Only works for independent tables (no foreign key conflicts)

## Troubleshooting

### Migration Hangs

**Symptom:** Progress bar stuck, no output

**Cause:** Large transaction or PostgreSQL lock

**Solution:**

```bash
# Check PostgreSQL activity
docker exec -it postgresql psql -U alloydbusr -d devto_analytics -c "
SELECT pid, state, query 
FROM pg_stat_activity 
WHERE state = 'active';
"

# Kill stuck query (if needed)
docker exec -it postgresql psql -U alloydbusr -d devto_analytics -c "
SELECT pg_terminate_backend(PID);
"
```

### Out of Memory

**Symptom:** Script crashes with MemoryError

**Solution:**

```bash
# Reduce batch size
python -m app.migrate_from_sqlite --batch-size 100

# Or migrate tables one at a time
python -m app.migrate_from_sqlite --tables snapshots
python -m app.migrate_from_sqlite --tables article_metrics
# etc.
```

### Connection Errors

**Symptom:** `Could not connect to PostgreSQL`

**Solution:**

```bash
# Verify PostgreSQL is running
docker ps | grep postgresql

# Check connection from container
docker exec -it devto_fastapi python -c "
from app.db.connection import get_async_engine
import asyncio

async def test():
    engine = get_async_engine()
    async with engine.begin() as conn:
        result = await conn.execute('SELECT 1')
        print('Connected:', result.scalar())

asyncio.run(test())
"
```

### SQLite File Not Found

**Symptom:** `Error: SQLite file not found`

**Solution:**

```bash
# Check file location in container
docker exec -it devto_fastapi ls -lh /code/devto_metrics.db

# Copy from host if needed
docker cp devto_metrics.db devto_fastapi:/code/
```

## Post-Migration Tasks

### 1. Verify Services

```bash
# Check FastAPI health (should see database data)
curl http://localhost:8000/api/health

# Test article endpoints
curl http://localhost:8000/api/articles/quality-scores | jq
```

### 2. Update Streamlit

Streamlit dashboard should now show historical data:

```bash
# Restart Streamlit to refresh cache
docker restart devto_streamlit

# Open in browser
# https://streamlit.weeklydigest.me
```

### 3. Configure Superset

Set up dashboards with migrated data:

```bash
# Access Superset
# https://dashboard.weeklydigest.me
# Login: admin / (your POSTGRES_PASSWORD)

# Add SQL queries to verify data
SELECT COUNT(*) as total_articles FROM devto_analytics.article_metrics;
SELECT COUNT(*) as total_views FROM devto_analytics.daily_analytics;
```

### 4. Clean Up

```bash
# Keep SQLite backup (recommended)
docker exec -it devto_fastapi mv devto_metrics.db devto_metrics.db.backup

# Or remove SQLite file
docker exec -it devto_fastapi rm devto_metrics.db

# Clean up logs
rm migration.log migration_checkpoint.json
```

## Rollback Procedure

If migration has issues, rollback:

```bash
# 1. Stop services
docker compose stop fastapi streamlit superset

# 2. Drop and recreate schema
docker exec -it postgresql psql -U alloydbusr -d postgres << 'EOF'
DROP SCHEMA IF EXISTS devto_analytics CASCADE;
CREATE SCHEMA devto_analytics;
EOF

# 3. Reinitialize schema
docker exec -it devto_fastapi python app/init_database.py

# 4. Restart services
docker compose start fastapi streamlit superset

# 5. Re-run migration
docker exec -it devto_fastapi python -m app.migrate_from_sqlite
```

## Expected Output

### Successful Migration

```
╔═══════════════════════════════════════════════════════════════╗
║               SQLite → PostgreSQL Migration                    ║
╚═══════════════════════════════════════════════════════════════╝

Mode: LIVE MIGRATION
SQLite: devto_metrics.db
Tables: 13
Batch Size: 1000

snapshots          ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 71/71    100%
article_metrics    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 3324/3324 100%
follower_events    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 84/84    100%
comments           ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 120/120  100%
followers          ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 0/0      100%
daily_analytics    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2292/2292 100%
referrers          ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 387/387  100%
article_content    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 24/24    100%
article_code_blocks ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 147/147  100%
article_links      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 95/95    100%
article_history    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 46/46    100%
milestone_events   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2/2      100%
comment_insights   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 59/59    100%

🔍 Validating Migration...

Validation Results
┌─────────────────────┬────────┬──────────────────┬──────────┐
│ Table               │ Status │ PostgreSQL Count │ Expected │
├─────────────────────┼────────┼──────────────────┼──────────┤
│ snapshots           │   ✓    │       71         │    71    │
│ article_metrics     │   ✓    │      3324        │   3324   │
│ follower_events     │   ✓    │       84         │    84    │
│ comments            │   ✓    │      120         │   120    │
│ daily_analytics     │   ✓    │      2292        │   2292   │
│ referrers           │   ✓    │      387         │   387    │
│ article_content     │   ✓    │       24         │    24    │
│ article_code_blocks │   ✓    │      147         │   147    │
│ article_links       │   ✓    │       95         │    95    │
│ article_history     │   ✓    │       46         │    46    │
│ milestone_events    │   ✓    │        2         │     2    │
│ comment_insights    │   ✓    │       59         │    59    │
└─────────────────────┴────────┴──────────────────┴──────────┘

🔄 Migration Summary
┌─────────────────────┬───────┬──────────┬─────────┬────────┐
│ Table               │ Total │ Inserted │ Skipped │ Errors │
├─────────────────────┼───────┼──────────┼─────────┼────────┤
│ snapshots           │   71  │    71    │    0    │   0    │
│ article_metrics     │  3324 │   3324   │    0    │   0    │
│ follower_events     │   84  │    84    │    0    │   0    │
│ comments            │  120  │   120    │    0    │   0    │
│ followers           │    0  │     0    │    0    │   0    │
│ daily_analytics     │  2292 │   2292   │    0    │   0    │
│ referrers           │  387  │   387    │    0    │   0    │
│ article_content     │   24  │    24    │    0    │   0    │
│ article_code_blocks │  147  │   147    │    0    │   0    │
│ article_links       │   95  │    95    │    0    │   0    │
│ article_history     │   46  │    46    │    0    │   0    │
│ milestone_events    │    2  │     2    │    0    │   0    │
│ comment_insights    │   59  │    59    │    0    │   0    │
├─────────────────────┼───────┼──────────┼─────────┼────────┤
│ TOTAL               │ 6651  │   6651   │    0    │   0    │
└─────────────────────┴───────┴──────────┴─────────┴────────┘

╔═══════════════════════════════════════════════════════════════╗
║                     Migration Results                          ║
╠═══════════════════════════════════════════════════════════════╣
║ ✅ COMPLETED                                                   ║
║                                                                ║
║ Duration: 42.3 seconds                                         ║
║ Total records: 6,651                                           ║
║ Inserted: 6,651                                                ║
║ Skipped: 0                                                     ║
║ Errors: 0                                                      ║
╚═══════════════════════════════════════════════════════════════╝
```

## Files Created

- `migration.log` - Detailed migration log
- `migration_checkpoint.json` - Resume checkpoint (if interrupted)

## Support

For issues:

1. Check `migration.log` for detailed errors
2. Review this guide's Troubleshooting section
3. Run `--dry-run` to test without changes
4. Try migrating one table at a time
5. Check PostgreSQL logs: `docker logs postgresql`

---

**Last Updated:** 2026-01-31  
**Script Version:** 1.0.0  
**Compatible With:** PostgreSQL 18, SQLite 3.x
