# Analytics Service Fixes - January 25, 2026

## Problem Summary

The analytics dashboard was showing incorrect data:
- Engagement rates >100% (inflated)
- Duplicate articles in results
- Incorrect read completion calculations
- Mismatched data between sources

## Root Causes

### 1. Data Structure Misunderstanding
**article_metrics**: Time-series table with multiple snapshots per article
- Each row is a complete snapshot at collection time
- Contains lifetime totals (views, reactions, comments)
- Multiple rows per article_id with different collected_at timestamps

**daily_analytics**: Daily breakdown (90-day window from DEV.to API)
- `page_views`: Daily count (can SUM for period total)
- `total_read_time_seconds`: Daily total (can SUM for weighted average)
- `reactions_total`, `comments_total`: Cumulative values (DON'T SUM)

### 2. Specific Issues Fixed

#### A. Duplicate Articles
**Problem**: Using `ROW_NUMBER()` window function for deduplication
**Solution**: PostgreSQL-specific `DISTINCT ON` - more efficient and cleaner
```sql
-- BEFORE (complex)
SELECT * FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY article_id ORDER BY collected_at DESC) as rn
  FROM article_metrics
) WHERE rn = 1

-- AFTER (PostgreSQL DISTINCT ON)
SELECT DISTINCT ON (article_id) *
FROM article_metrics
ORDER BY article_id, collected_at DESC
```

#### B. Incorrect Engagement Rates (>100%)
**Problem**: Summing cumulative values from daily_analytics
```python
# WRONG: reactions_total and comments_total are cumulative
reactions = SUM(daily_analytics.reactions_total)  # Double/triple counting!
engagement = (reactions + comments) / views_90d   # Result: 200%+
```

**Solution**: Use latest snapshot from article_metrics
```python
# CORRECT: Use lifetime totals from latest snapshot
latest_snapshot = DISTINCT ON (article_id) article_metrics
engagement = (latest_snapshot.reactions + latest_snapshot.comments) / latest_snapshot.views
```

**Results**:
- BEFORE: Engagement 40.7%, 106.9%, 200%+ (clearly wrong)
- AFTER: Engagement 3.7-11.0% (realistic for DEV.to)

#### C. Incorrect 90-Day Traffic
**Problem**: Using `MAX(page_views)` - only captured single day's max
```python
# WRONG: Gets one day's value, not 90-day total
views_90d = MAX(daily_analytics.page_views)  # e.g., 42 views
```

**Solution**: Sum daily values
```python
# CORRECT: Aggregate all daily page views
views_90d = SUM(daily_analytics.page_views)  # e.g., 2,500 views
```

#### D. Incorrect Read Completion (Average of Averages)
**Problem**: Taking average of daily averages
```python
# WRONG: "Average of averages" is mathematically invalid
avg_read = AVG(daily_analytics.average_read_time_seconds)
# Day 1: 5 views, 300s avg → contributes 300 to average
# Day 2: 500 views, 100s avg → contributes 100 to average
# Result heavily biased toward low-traffic days
```

**Solution**: Weighted average using totals
```python
# CORRECT: Total read time / total views
total_read = SUM(daily_analytics.total_read_time_seconds)
total_views = SUM(daily_analytics.page_views)
avg_read = total_read / total_views  # Properly weighted
completion = (avg_read / (reading_time_minutes * 60)) * 100
```

**Formula**: `(SUM(total_read_time_seconds) / SUM(page_views)) / (reading_time_minutes * 60) * 100`

## Changes Made

### Files Modified
1. **app/services/analytics_service.py** (116 insertions, 96 deletions)
   - `get_read_time_analysis()`: Fixed deduplication, weighted avg, SUM views
   - `get_quality_scores()`: Fixed engagement source, weighted avg, DISTINCT ON
   - `get_long_tail_champions()`: Fixed deduplication to DISTINCT ON
   - `refresh_all_stats()`: Applied all same fixes for cache consistency

### Commits
1. `962bc71` - Fix duplicate articles in analytics dashboard (ROW_NUMBER deduplication)
2. `4997784` - Fix analytics calculations: correct engagement rates and read completion

## Validation

### Before
```
⭐ QUALITY SCORES (90-day performance)
Title                                      Quality   Read %   Engage %
Actually Agile...                           100.0   100.0%     40.7%  ❌ Unrealistic
From WordPress to Astro...                   57.0    49.3%     15.0%  ❌ Still high
Why Streamlit + Cloud Run...                 33.9     5.5%    106.9%  ❌ IMPOSSIBLE!
```

### After
```
⭐ QUALITY SCORES (90-day performance)
Title                                      Quality   Read %   Engage %
Building with AI without losing control..    86.5   100.0%     11.0%  ✅ Realistic
Respiration                                  83.2   100.0%      8.8%  ✅ Realistic
Actually Agile...                            75.9   100.0%      3.9%  ✅ Realistic
```

### Test Commands
```bash
# View dashboard
python3 -m app.services.analytics_service

# Refresh cache
python3 -m app.services.analytics_service --refresh
```

## Business Logic Preserved

All original formulas maintained:
- **Quality Score**: `(completion * 0.7) + (min(engagement, 20) * 1.5)`
- **Engagement Cap**: 20% maximum (30% weight in quality score)
- **Completion Cap**: 100% maximum (70% weight in quality score)

Only the **data sources** were corrected, not the business logic.

## Technical Patterns Established

### For Future Queries
1. **Get latest article snapshot**: Use `DISTINCT ON (article_id)` ordered by `collected_at DESC`
2. **Aggregate 90d traffic**: Use `SUM(daily_analytics.page_views)` - daily values
3. **Calculate read time**: Use `SUM(total_read_time_seconds) / SUM(page_views)` - weighted avg
4. **Get engagement**: Use latest `article_metrics` snapshot, NOT daily_analytics aggregates
5. **Avoid**: Summing cumulative columns (reactions_total, comments_total, follows_total)

## Impact

✅ **Engagement rates realistic**: Now showing 3-11% (typical for technical content)  
✅ **No duplicates**: Each article appears once  
✅ **Accurate read metrics**: Properly weighted by view count  
✅ **Cache consistency**: refresh_all_stats() uses same corrected logic  
✅ **Data integrity**: article_metrics (source of truth) vs daily_analytics (90d window)  

The analytics dashboard now provides accurate, actionable insights based on correct data interpretation.
