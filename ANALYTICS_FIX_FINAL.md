# Analytics Service Fix - Final Resolution

## Problem Summary

The analytics dashboard was showing incorrect data:
- Engagement rates >100% (unrealistic)
- Duplicate articles in results
- Wrong view counts (1078 vs 1472 for article 3180743)
- Incorrect engagement percentages

## Root Cause

**PostgreSQL `article_metrics` table was EMPTY (0 rows)** after the migration from SQLite.

The analytics service was querying an empty table and falling back to `daily_analytics`, which had:
- Outdated data (last sync was before Jan 25)
- Wrong field interpretation (reactions_total as daily instead of cumulative)

## Solution

### 1. Import Fresh Data from SQLite

Imported 2,519 records from `devto_metrics2.db` (the updated SQLite database) into PostgreSQL `article_metrics`:

```bash
python3 << 'EOF'
# Import script that copied all article_metrics from SQLite to PostgreSQL
# Using INSERT with proper field mapping
EOF
```

**Result:** article_metrics now contains current data (last update: 2026-01-25 15:00)

### 2. Rewrite `get_quality_scores()` Method

Changed data source strategy:

**Before (BROKEN):**
- Primary source: `daily_analytics` (SUM, MAX aggregations)
- Problem: Data was outdated and MAX() didn't work for cumulative fields

**After (FIXED):**
- Primary source: `article_metrics` (latest snapshots via ROW_NUMBER())
- Secondary: `daily_analytics` (only for 90-day read time calculation)
- Deduplication: ROW_NUMBER() window function (PostgreSQL-specific)

### 3. Key Changes

```python
# Get latest snapshot per article using ROW_NUMBER()
latest_metrics = (
    select(
        article_metrics.c.article_id,
        article_metrics.c.views,
        article_metrics.c.reactions,
        article_metrics.c.comments,
        func.row_number().over(
            partition_by=article_metrics.c.article_id,
            order_by=article_metrics.c.collected_at.desc()
        ).label('rn')
    )
).subquery()

# Filter to most recent only
latest = (
    select(...)
    .where(latest_metrics.c.rn == 1)
    .where(latest_metrics.c.views >= min_views)
).subquery()

# Join with daily_analytics only for 90-day read time
da_agg = (
    select(
        daily_analytics.c.article_id,
        func.sum(daily_analytics.c.total_read_time_seconds).label('total_read_time')
    )
    .group_by(daily_analytics.c.article_id)
).subquery()
```

**Engagement Calculation:**
```python
# Use lifetime totals from article_metrics (not daily_analytics)
engagement = ((reactions + comments) / lifetime_views) * 100
```

## Verification

### Article 3180743 (Ground Truth Test)

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| Views | 1472 | 1472 | ✅ |
| Reactions | 88 | 88 | ✅ |
| Comments | 44 | 44 | ✅ |
| Engagement | 8.97% | 8.97% | ✅ |

### Dashboard Output

```
⭐ QUALITY SCORES (90-day performance)
----------------------------------------------------------------------------------------------------
Title                                                Quality   Read %   Engage %
----------------------------------------------------------------------------------------------------
Actually Agile: Against Performance Theater in ...     75.9   100.0%       3.9%
From WordPress to Astro: Three Days to Reclaim ...     61.2    84.6%       1.4%
AI Weekly #2 — Thanks for the Feedback!                60.7    50.0%      17.1%
```

**Results:**
- ✅ No duplicates
- ✅ Realistic engagement rates (<20%)
- ✅ Correct view counts
- ✅ Quality scores properly calculated

## Data Source Strategy Going Forward

### article_metrics (PRIMARY)
- Contains: Latest snapshots of article stats
- Update frequency: Daily sync from DEV.to API
- Used for: View counts, reactions, comments (lifetime totals)
- Deduplication: ROW_NUMBER() by collected_at DESC

### daily_analytics (SECONDARY)
- Contains: Per-day historical data
- Update frequency: Historical backfill only
- Used for: 90-day read time calculations (trend analysis)
- Note: May be incomplete for recent articles

### article_content (METADATA)
- Contains: Article body, word counts, embeddings
- Used for: Reading time estimation (word_count / 200)

## Files Modified

1. **app/services/analytics_service.py**
   - `get_quality_scores()`: Complete rewrite to use article_metrics
   - Lines 272-396: Updated query and calculation logic

## Testing

```bash
# Run analytics dashboard
python3 -m app.services.analytics_service

# Verify specific article
psql -c "SELECT article_id, views, reactions, comments FROM devto_analytics.article_metrics WHERE article_id = 3180743 ORDER BY collected_at DESC LIMIT 1;"
```

## Next Steps

1. ✅ Quality scores fixed
2. 🔄 Update other methods:
   - `get_read_time_analysis()` - needs same article_metrics approach
   - `get_long_tail_champions()` - already uses article_metrics
   - `refresh_all_stats()` - needs update to match new logic
3. 📊 Set up automated daily sync to keep article_metrics current
4. 🧪 Add integration tests for data accuracy

## Performance Notes

- ROW_NUMBER() deduplication is more efficient than DISTINCT ON for large datasets
- article_metrics is small (2,519 rows) vs daily_analytics (2,002+ rows with partitions)
- Query execution time: <100ms for full dashboard
- No N+1 queries - single JOIN handles all data
