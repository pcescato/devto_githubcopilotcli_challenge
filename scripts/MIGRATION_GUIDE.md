# SQLite to PostgreSQL Migration Guide

## Overview

The migration script (`scripts/migrate_sqlite_to_postgres.py`) transfers data from your existing SQLite database (`devto_metrics.db`) to the new PostgreSQL 18 schema with full data transformation and error handling.

## Features

✅ **Schema-Aware**: Uses `app/db/tables.py` for accurate column mapping  
✅ **Data Transformations**: Handles tags, dates, JSONB, arrays  
✅ **Batch Processing**: 1,000 rows per batch for performance  
✅ **Progress Tracking**: Real-time progress bars with tqdm  
✅ **Idempotent**: ON CONFLICT DO NOTHING for safe re-runs  
✅ **Error Handling**: Detailed logging and fallback strategies  
✅ **Dependency Order**: Respects foreign key relationships  

## Prerequisites

1. **PostgreSQL schema initialized**:
   ```bash
   cd app
   python3 init_database.py
   ```

2. **Dependencies installed**:
   ```bash
   pip install tqdm python-dateutil
   ```

3. **SQLite database exists**:
   ```bash
   ls -lh devto_metrics.db
   ```

4. **Environment configured** (`.env`):
   ```bash
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=devto
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=devto_analytics
   ```

## Quick Start

```bash
# From project root
python3 scripts/migrate_sqlite_to_postgres.py
```

## What It Does

### 1. Connection Verification
- Checks SQLite database exists
- Verifies PostgreSQL connection
- Validates schema is initialized

### 2. Data Transformations

#### Tags Conversion
```python
# SQLite (JSON string or CSV)
'["python", "postgresql"]'  → ['python', 'postgresql']  # ARRAY(String)
'python,postgresql'         → ['python', 'postgresql']
```

#### DateTime Conversion
```python
# ISO strings → timezone-aware UTC
'2024-01-23T12:34:56Z' → datetime(2024, 1, 23, 12, 34, 56, tzinfo=UTC)
'2024-01-23 12:34:56'  → datetime(2024, 1, 23, 12, 34, 56, tzinfo=UTC)
```

#### JSONB Conversion
```python
# JSON string → Python dict
'{"key": "value"}' → {'key': 'value'}  # JSONB in PostgreSQL
```

#### Column Mapping
```python
# SQLite → PostgreSQL
page_views_count → views
page_views       → views
```

### 3. Migration Order

Tables are migrated in dependency order (from `get_all_tables()`):

```
1.  snapshots
2.  article_metrics
3.  comments
4.  followers
5.  follower_events
6.  daily_analytics
7.  referrers
8.  article_content
9.  article_code_blocks
10. article_links
11. comment_insights
12. article_history
13. milestone_events
14. author_themes
15. article_theme_mapping
16. article_stats_cache
17. tag_evolution
18. quality_scores
```

### 4. Batch Processing

- Reads 1,000 rows at a time
- Transforms each row
- Inserts batch with `ON CONFLICT DO NOTHING`
- Progress bar shows real-time status

### 5. Error Handling

**Table not found in SQLite:**
```
⚠️  Table 'article_code_blocks' not found in SQLite
```
→ Skips table, continues migration

**Data transformation error:**
```
⚠️  Error transforming row: invalid date format
```
→ Logs error, skips row, continues batch

**Insert error:**
```
❌ Error inserting batch: unique constraint violation
```
→ Retries row-by-row to identify problem

## Expected Output

```
======================================================================
🚀 SQLite → PostgreSQL Migration
======================================================================

1️⃣ Checking connections...
  ✅ SQLite: /path/to/devto_metrics.db
  ✅ PostgreSQL: Connected

2️⃣ Verifying PostgreSQL schema...
  ✅ Found 18 tables in devto_analytics schema

3️⃣ Planning migration order...
  ✅ Will migrate 18 tables in dependency order

📋 Migration order:
   1. snapshots
   2. article_metrics
   3. comments
   ...

⚠️  This will migrate data from SQLite to PostgreSQL.
    Existing data in PostgreSQL will be preserved (ON CONFLICT DO NOTHING).

   Continue? [y/N]: y

4️⃣ Migrating data...
======================================================================

📊 Migrating snapshots...
  snapshots: 100%|███████████████████| 50/50 [00:00<00:00, 500 rows/s]
  ✅ Migrated: 50/50 rows

📊 Migrating article_metrics...
  article_metrics: 100%|██████████| 1500/1500 [00:02<00:00, 750 rows/s]
  ✅ Migrated: 1500/1500 rows

📊 Migrating comments...
  comments: 100%|████████████████| 300/300 [00:00<00:00, 600 rows/s]
  ✅ Migrated: 300/300 rows

...

======================================================================
✅ Migration Complete!
======================================================================

📊 Summary:
  • Total rows migrated: 3,850
  • Successful tables: 18/18

🔍 Verification:
  Run these commands to verify:
    psql devto_analytics -c "SELECT COUNT(*) FROM devto_analytics.article_metrics;"
    psql devto_analytics -c "SELECT COUNT(*) FROM devto_analytics.comments;"
```

## Verification

### Check Row Counts

```bash
# Compare counts
sqlite3 devto_metrics.db "SELECT COUNT(*) FROM article_metrics;"
psql devto_analytics -c "SELECT COUNT(*) FROM devto_analytics.article_metrics;"
```

### Sample Data Check

```bash
# PostgreSQL
psql devto_analytics -c "
SELECT article_id, title, views, tag_list 
FROM devto_analytics.article_metrics 
ORDER BY collected_at DESC 
LIMIT 5;
"

# SQLite
sqlite3 devto_metrics.db "
SELECT article_id, title, views, tags 
FROM article_metrics 
ORDER BY collected_at DESC 
LIMIT 5;
"
```

### Check Data Types

```sql
-- PostgreSQL: Verify tag_list is array
SELECT article_id, tag_list, array_length(tag_list, 1) as tag_count
FROM devto_analytics.article_metrics
WHERE tag_list IS NOT NULL
LIMIT 5;

-- Verify datetime timezone
SELECT collected_at, pg_typeof(collected_at)
FROM devto_analytics.article_metrics
LIMIT 1;
```

## Troubleshooting

### Error: "Schema 'devto_analytics' not found"

**Solution**: Initialize PostgreSQL schema first
```bash
cd app
python3 init_database.py
```

### Error: "No module named 'tqdm'"

**Solution**: Install dependencies
```bash
pip install tqdm python-dateutil
```

### Error: "SQLite database not found"

**Solution**: Ensure database exists in project root
```bash
ls -lh devto_metrics.db
# If missing, collect data first:
python devto_tracker.py --collect
```

### Error: "Connection refused"

**Solution**: Check PostgreSQL is running and credentials are correct
```bash
# Test connection
psql -h localhost -U devto -d devto_analytics -c "SELECT 1;"

# Check .env file
cat .env | grep POSTGRES
```

### Warning: "⚠️  X errors"

**Causes**:
- Invalid date formats → Skipped rows
- Extra columns in SQLite → Automatically ignored
- Missing required fields → Logged and skipped

**Action**: Check logs for specific errors. Migration continues with valid rows.

## Re-running Migration

The script is **idempotent** (safe to run multiple times):

```bash
# Subsequent runs skip existing data
python3 scripts/migrate_sqlite_to_postgres.py
```

All inserts use `ON CONFLICT DO NOTHING`, so:
- ✅ Existing data is preserved
- ✅ Only new rows are added
- ✅ No duplicates created

## Performance

### Typical Performance

| Rows | Time | Speed |
|------|------|-------|
| 1,000 | 1-2s | ~500-1000 rows/s |
| 10,000 | 10-20s | ~500-1000 rows/s |
| 100,000 | 2-3 min | ~500-1000 rows/s |

### Optimization

**Increase batch size** (for large datasets):
```python
# In migrate_sqlite_to_postgres.py
BATCH_SIZE = 5000  # Default: 1000
```

**Disable indexes temporarily** (for very large migrations):
```sql
-- Before migration
DROP INDEX devto_analytics.ix_article_metrics_article_id;

-- After migration
CREATE INDEX ix_article_metrics_article_id 
ON devto_analytics.article_metrics(article_id);
```

## Advanced Usage

### Migrate Specific Tables

Edit script to filter tables:
```python
# In main()
tables_to_migrate = [t for t in get_all_tables() if t.name in ['article_metrics', 'comments']]
```

### Dry Run (Check Only)

```python
# In migrate_table()
# Comment out insert line:
# result = conn.execute(stmt)
print(f"Would insert {len(transformed_rows)} rows")
```

### Export Migration Report

```bash
# Redirect output to file
python3 scripts/migrate_sqlite_to_postgres.py 2>&1 | tee migration.log
```

## Data Transformations Reference

### Tags Field

| SQLite Format | PostgreSQL `tag_list` (ARRAY) | PostgreSQL `tags` (JSONB) |
|---------------|-------------------------------|---------------------------|
| `'["python"]'` | `['python']` | `['python']` |
| `'python,sql'` | `['python', 'sql']` | N/A (if tag_list exists) |
| `NULL` | `NULL` | `NULL` |

### Date Fields

All date/datetime fields are converted to **timezone-aware UTC**:
- `collected_at`
- `published_at`
- `created_at`
- `followed_at`
- `occurred_at`
- `date`
- `changed_at`
- `classified_at`

### JSONB Fields

JSON strings are parsed to Python dicts:
- `tags` (in article_content)
- `keywords`
- `named_entities`
- `main_topics`

## Next Steps

After successful migration:

1. **Verify data integrity**:
   ```bash
   psql devto_analytics -c "SELECT * FROM devto_analytics.get_table_sizes();"
   ```

2. **Run analytics queries**:
   ```bash
   python quality_analytics.py
   ```

3. **Test business logic**:
   ```bash
   cd app
   python3 -c "
   from app.db.connection import get_connection
   from app.db.queries import calculate_quality_scores
   with get_connection() as conn:
       result = calculate_quality_scores(conn)
       print(result)
   "
   ```

4. **Set up continuous collection**:
   ```bash
   python devto_tracker.py --collect
   ```

## Support

- **Script Location**: `scripts/migrate_sqlite_to_postgres.py`
- **Documentation**: This file
- **Schema Reference**: `app/db/tables.py`
- **Connection Patterns**: `app/db/connection.py`

---

**Status**: Production-ready migration tool  
**Safety**: Idempotent, preserves existing data  
**Performance**: ~500-1000 rows/second
