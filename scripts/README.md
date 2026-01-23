# Migration Scripts

Utilities for migrating data from SQLite to PostgreSQL.

## Scripts

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
