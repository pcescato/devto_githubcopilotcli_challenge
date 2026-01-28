# Scripts Directory

Utilities for database migration, automated sync workers, and maintenance.

## Files

- **`sync_worker.py`** - Automated sync worker for cron (NEW - 2026-01-28)
- `migrate_sqlite_to_postgres.py` - Migrate data from SQLite to PostgreSQL
- `MIGRATION_GUIDE.md` - Complete migration documentation
- `requirements.txt` - Python dependencies

---

## 🔄 Sync Worker (Production)

### Overview

`sync_worker.py` - Standalone async worker for automated data synchronization via cron.

**Pipeline Phases:**
1. **Collection** - Fetch latest article metrics from DEV.to API
2. **Enrichment** - Sync 90-day historical analytics  
3. **Intelligence** - Classify articles by theme (DNA analysis)
4. **Refresh Cache** - Update materialized views

### Features

✅ **Asynchronous execution** - Efficient I/O with AsyncIO  
✅ **PostgreSQL advisory locks** - Prevents concurrent runs  
✅ **Idempotent operations** - Safe to run multiple times  
✅ **Cron-friendly** - Proper exit codes for monitoring  
✅ **Timestamped logging** - Easy debugging  

### Quick Start

```bash
# Manual execution
python3 scripts/sync_worker.py

# Expected output:
# [2026-01-28 09:30:00] 🚀 Starting Sync Pipeline...
# [2026-01-28 09:30:15] ✅ Collection: 25 articles updated in 13.2s
# [2026-01-28 09:30:45] ✅ Enrichment: 2250 snapshots synced in 30.1s
# [2026-01-28 09:30:50] ✅ Intelligence: 25 articles classified in 5.3s
# [2026-01-28 09:30:51] ✅ Cache refresh completed in 0.8s
# [2026-01-28 09:30:51] 🎉 Pipeline completed successfully in 49.4s
```

### Cron Configuration

```bash
# Edit crontab
crontab -e

# Hourly sync at minute 5
5 * * * * cd /path/to/devto_githubcopilotcli_challenge && python3 scripts/sync_worker.py >> logs/sync_worker.log 2>&1

# Or every 6 hours (balanced - recommended)
5 0,6,12,18 * * * cd /path/to/devto_githubcopilotcli_challenge && python3 scripts/sync_worker.py >> logs/sync_worker.log 2>&1

# Or daily at 2 AM (low frequency)
5 2 * * * cd /path/to/devto_githubcopilotcli_challenge && python3 scripts/sync_worker.py >> logs/sync_worker.log 2>&1
```

### Environment Variables

Loads from `.env` in project root:

```env
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=devto_analytics
POSTGRES_USER=devto
POSTGRES_PASSWORD=your_secure_password

# DEV.to API
DEVTO_API_KEY=your_devto_api_key
DEVTO_USERNAME=your_username
```

### Monitoring

```bash
# View live logs
tail -f logs/sync_worker.log

# Check for errors
grep "ERROR" logs/sync_worker.log

# Count successful runs today
grep "Pipeline completed successfully" logs/sync_worker.log | grep "$(date +%Y-%m-%d)" | wc -l

# View summary stats
grep "SYNC SUMMARY" logs/sync_worker.log -A 5
```

### Exit Codes

- **0** - Success or lock unavailable (normal, safe for cron)
- **1** - Error occurred (check logs for stack trace)

### Advisory Lock

Uses PostgreSQL advisory lock (ID: `98765`) to prevent concurrent execution.

**Check active locks:**
```sql
SELECT * FROM pg_locks WHERE locktype = 'advisory';
```

**Force release (emergency only):**
```sql
SELECT pg_advisory_unlock(98765);
```

### Performance

Expected durations for ~25 articles:
- Collection: 10-20 seconds
- Enrichment: 30-60 seconds (90 days)
- Intelligence: 5-10 seconds
- Cache Refresh: 1-3 seconds
- **Total: 50-90 seconds**

### Troubleshooting

**Lock always held:**
```sql
-- Release manually
SELECT pg_advisory_unlock(98765);
```

**Import errors:**
```bash
# Run from project root
cd /path/to/devto_githubcopilotcli_challenge
python3 scripts/sync_worker.py
```

**API rate limiting:**
- Reduce cron frequency (e.g., every 6 hours instead of hourly)
- Check API key: `curl -H "api-key: YOUR_KEY" https://dev.to/api/articles/me/all`

---

## 🗄️ Migration Scripts

### `migrate_sqlite_to_postgres.py`

Main migration script that transfers data from `devto_metrics.db` (SQLite) to PostgreSQL 18.

**Features:**
- ✅ Schema-aware using `app/db/tables.py`
- ✅ Batch processing (1,000 rows per batch)
- ✅ Progress bars with tqdm
- ✅ Data transformations (tags, dates, JSONB)
- ✅ ON CONFLICT handling for idempotency
- ✅ Dependency-aware table ordering
- ✅ Comprehensive error handling

**Usage:**
```bash
python3 scripts/migrate_sqlite_to_postgres.py
```

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for complete documentation.

## Installation

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Or if you already installed app/requirements.txt, just add:
pip install tqdm python-dateutil
```

## Prerequisites

1. **Initialize PostgreSQL schema:**
   ```bash
   cd app
   python3 init_database.py
   ```

2. **Configure environment** (`.env`):
   ```bash
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=devto
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=devto_analytics
   ```

3. **Ensure SQLite database exists:**
   ```bash
   ls -lh devto_metrics.db
   ```

## Quick Start

```bash
# 1. Check you're in project root
pwd
# Should show: /path/to/devto_githubcopilotcli_challenge

# 2. Run migration
python3 scripts/migrate_sqlite_to_postgres.py

# 3. Verify
psql devto_analytics -c "SELECT * FROM devto_analytics.get_table_sizes();"
```

## What Gets Migrated

All tables from SQLite schema:
- ✅ snapshots
- ✅ article_metrics
- ✅ comments
- ✅ followers
- ✅ follower_events
- ✅ daily_analytics
- ✅ referrers
- ✅ article_content
- ✅ article_code_blocks
- ✅ article_links
- ✅ comment_insights
- ✅ article_history
- ✅ milestone_events
- ✅ author_themes
- ✅ article_theme_mapping
- ✅ article_stats_cache
- ✅ tag_evolution
- ✅ quality_scores

## Data Transformations

### Tags
```python
# SQLite → PostgreSQL
'["python", "sql"]' → ['python', 'sql']  # ARRAY(String)
'python,sql'        → ['python', 'sql']
```

### Dates
```python
# All dates → timezone-aware UTC
'2024-01-23T12:34:56Z' → datetime(2024, 1, 23, 12, 34, 56, tzinfo=UTC)
```

### JSONB
```python
# JSON strings → Python dicts
'{"key": "value"}' → {'key': 'value'}
```

## Safety

The migration is **idempotent** (safe to run multiple times):
- Uses `INSERT ... ON CONFLICT DO NOTHING`
- Existing data is preserved
- Only new rows are added
- No duplicates created

## Performance

Typical speed: **500-1000 rows/second**

| Dataset Size | Expected Time |
|--------------|---------------|
| 1,000 rows | 1-2 seconds |
| 10,000 rows | 10-20 seconds |
| 100,000 rows | 2-3 minutes |

## Troubleshooting

### Common Issues

**"Schema not found"**
```bash
python3 app/init_database.py
```

**"Connection refused"**
```bash
# Check PostgreSQL is running
docker-compose ps postgres
# or
systemctl status postgresql
```

**"Module not found"**
```bash
pip install -r scripts/requirements.txt
```

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for detailed troubleshooting.

## Files

```
scripts/
├── README.md                      # This file
├── MIGRATION_GUIDE.md             # Complete documentation
├── migrate_sqlite_to_postgres.py  # Main migration script
└── requirements.txt               # Python dependencies
```

## Next Steps

After migration:
1. Verify data integrity
2. Run analytics queries
3. Test business logic
4. Set up continuous collection

See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for detailed next steps.

---

**Status**: Production-ready  
**Safety**: Idempotent, preserves data  
**Performance**: ~500-1000 rows/s
