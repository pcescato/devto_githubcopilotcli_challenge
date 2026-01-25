# CRITICAL: Data Source Issue Discovered

## Problem
Analytics queries return 0 results because they join `article_metrics` (EMPTY) with `daily_analytics` (HAS DATA).

## Current Database State  
```
article_metrics:    0 rows    ← EMPTY!
article_content:   24 rows    ← Has titles, metadata
daily_analytics: 2002 rows    ← Has ALL metrics data
```

## Root Cause
The PostgreSQL migration populated `daily_analytics` from historical.json but `article_metrics` was never populated (requires separate API sync).

## User's Report Confirmed
- User said article 3180743 shows **1078 views** (from article_metrics) 
- But should show **1472 views** (from daily_analytics SUM)
- Query confirms: 0 rows in article_metrics, 91 rows in daily_analytics for this article

## Required Fix
Rewrite `get_quality_scores()` to:
1. Use `daily_analytics` as PRIMARY source (not article_metrics)
2. JOIN with `article_content` for titles/metadata
3. Aggregate from daily_analytics:
   - Views: `SUM(page_views)`
   - Reactions: `MAX(reactions_total)` (cumulative field)
   - Comments: `MAX(comments_total)` (cumulative field)
   - Read time: `SUM(total_read_time_seconds) / SUM(page_views)`

## Expected Result for Article 3180743
Using daily_analytics data:
- Views: 1472 (SUM of 91 daily page_views)
- Reactions: 107 (MAX of reactions_total)
- Comments: 39 (MAX of comments_total)
- Engagement: 9.92% = (107 + 39) / 1472 * 100

This matches historical.json ground truth!

## Next Steps
1. Rewrite queries to use daily_analytics + article_content JOIN
2. Remove dependency on article_metrics (or make it optional fallback)
3. Run devto_service sync to populate article_metrics for future use
4. Update documentation about data sources
