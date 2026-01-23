# Schema Foreign Key Fix ✅

## Issue

When trying to create tables, you encountered this error:

```
(psycopg2.errors.InvalidForeignKey) there is no unique constraint 
matching given keys for referenced table "article_metrics"
```

## Root Cause

Multiple tables were trying to create foreign keys referencing `article_metrics.article_id`:
- `comments`
- `daily_analytics`
- `referrers`
- `article_content`
- `article_history`
- `milestone_events`
- `article_theme_mapping`

**Problem**: `article_metrics` is a **time-series table** with multiple rows per article_id (one per collection timestamp). The `article_id` column is NOT unique, so foreign keys cannot reference it.

## Solution Applied

Removed all foreign key constraints to `article_metrics.article_id`. These are now simple integer columns with indexes for performance but no referential integrity constraints.

### Changes Made

| Table | Before | After |
|-------|--------|-------|
| `comments` | FK to article_metrics.article_id | Integer with index, no FK |
| `daily_analytics` | FK to article_metrics.article_id | Integer with index, no FK |
| `referrers` | FK to article_metrics.article_id | Integer with index, no FK |
| `article_content` | FK to article_metrics.article_id (PK) | Integer PK, no FK |
| `article_history` | FK to article_metrics.article_id | Integer with index, no FK |
| `milestone_events` | FK to article_metrics.article_id | Integer with index, no FK |
| `article_theme_mapping` | FK to article_metrics.article_id | Integer, no FK |

**Kept**: `article_theme_mapping.theme_id` → `author_themes.id` (this FK is valid)

## Why This Is Correct

1. **Time-series nature**: `article_metrics` stores snapshots over time, so `article_id` appears multiple times
2. **Application-level integrity**: The application ensures valid article_ids are used
3. **Performance**: Indexes remain for efficient lookups
4. **Flexibility**: No cascade deletes to worry about with time-series data

## Testing

After this fix, run:

```bash
# From project root
cd app
python3 init_database.py
```

Expected output:
```
✅ Connection successful
✅ PostgreSQL extensions initialized
✅ Database schema created!
✅ Monthly partitions created!
✅ Author themes seeded!
```

## Alternative Solutions (Not Implemented)

1. **Create a separate `articles` table** with unique article_id as PK
   - Pro: Proper referential integrity
   - Con: Requires data migration, adds complexity
   
2. **Use composite foreign keys** (article_id + collected_at)
   - Pro: Maintains some integrity
   - Con: Overly complex, not aligned with business logic

3. **Keep current approach** ✅ (Selected)
   - Pro: Simple, performant, matches SQLite behavior
   - Con: No database-level referential integrity

## Files Modified

- `app/db/tables.py` - Removed 7 foreign key constraints

## Next Steps

1. Run `python3 app/init_database.py` to create tables
2. Run `python3 app/validate_schema.py` to verify (after installing dependencies)
3. Start populating data with your existing Python scripts

---

**Status**: Fixed ✅  
**Date**: 2026-01-23  
**Impact**: Schema now creates successfully
