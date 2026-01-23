"""
Common Query Patterns
Preserves business logic from SQLite implementation with PostgreSQL optimizations
"""

from sqlalchemy import select, func, and_, or_, text, case
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .tables import (
    article_metrics,
    follower_events,
    comments,
    comment_insights,
    daily_analytics,
    article_content,
    article_stats_cache,
)


# ============================================================================
# FOLLOWER ATTRIBUTION (advanced_analytics.py:118-227)
# ============================================================================

def weighted_follower_attribution(conn, hours: int = 168):
    """
    Calculate follower attribution using Share of Voice algorithm
    
    Business Logic (advanced_analytics.py:118-227):
    1. Find follower gain in time window
    2. Calculate traffic gain per article
    3. Distribute followers proportionally: share * total_gain
    
    Args:
        conn: SQLAlchemy connection
        hours: Time window (default: 168 = 7 days)
    
    Returns:
        List of dicts with article attribution results
    """
    from .connection import find_closest_snapshot
    
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    # 1. Find follower gain (6-hour tolerance)
    f_start = find_closest_snapshot(
        conn, follower_events, 'collected_at', start_time, tolerance_hours=6
    )
    f_end = find_closest_snapshot(
        conn, follower_events, 'collected_at', end_time, tolerance_hours=6
    )
    
    if not f_start or not f_end:
        return []
    
    total_gain = f_end['follower_count'] - f_start['follower_count']
    if total_gain <= 0:
        return []
    
    # 2. Calculate view gain per article
    attribution_data = []
    global_traffic_gain = 0
    
    # Get all active articles
    articles_stmt = (
        select(
            article_metrics.c.article_id,
            func.max(article_metrics.c.title).label('title')
        )
        .where(article_metrics.c.is_deleted == False)
        .group_by(article_metrics.c.article_id)
    )
    
    articles = conn.execute(articles_stmt).mappings().all()
    
    for art in articles:
        # Find views at start
        v_start = find_closest_snapshot(
            conn, article_metrics, 'collected_at', start_time,
            additional_filters=[article_metrics.c.article_id == art['article_id']]
        )
        
        # Find views at end
        v_end = find_closest_snapshot(
            conn, article_metrics, 'collected_at', end_time,
            additional_filters=[article_metrics.c.article_id == art['article_id']]
        )
        
        if v_start and v_end:
            gain = v_end['views'] - v_start['views']
            if gain > 0:
                attribution_data.append({
                    'article_id': art['article_id'],
                    'title': art['title'],
                    'views_gain': gain
                })
                global_traffic_gain += gain
    
    if global_traffic_gain == 0:
        return []
    
    # 3. Calculate attribution (share of voice)
    results = []
    for item in attribution_data:
        share = item['views_gain'] / global_traffic_gain
        attributed_followers = share * total_gain
        
        results.append({
            **item,
            'traffic_share': share,
            'attributed_followers': attributed_followers
        })
    
    # Sort by attributed followers
    results.sort(key=lambda x: x['attributed_followers'], reverse=True)
    
    return results


# ============================================================================
# QUALITY SCORE (quality_analytics.py:260-328)
# ============================================================================

def calculate_quality_scores(conn, min_views: int = 20):
    """
    Calculate quality scores for all articles
    
    Formula (quality_analytics.py:301-302):
        quality_score = (completion × 0.7) + (min(engagement, 20) × 1.5)
    
    Where:
        completion = min(100, (avg_read / expected_time) × 100)
        engagement = ((reactions + comments) / views) × 100
    
    Args:
        conn: SQLAlchemy connection
        min_views: Minimum views to include (default: 20)
    
    Returns:
        List of dicts with quality metrics
    """
    # Query combines data from daily_analytics and article_metrics
    stmt = (
        select(
            article_metrics.c.article_id,
            func.max(article_metrics.c.title).label('title'),
            func.max(article_metrics.c.reading_time_minutes).label('reading_time_minutes'),
            func.avg(daily_analytics.c.average_read_time_seconds).label('avg_read_seconds'),
            func.max(daily_analytics.c.page_views).label('views_90d'),
            func.max(daily_analytics.c.reactions_total).label('reactions_90d'),
            func.max(daily_analytics.c.comments_total).label('comments_90d'),
        )
        .select_from(
            article_metrics.join(
                daily_analytics,
                article_metrics.c.article_id == daily_analytics.c.article_id
            )
        )
        .where(daily_analytics.c.page_views > 0)
        .group_by(article_metrics.c.article_id)
        .having(func.max(daily_analytics.c.page_views) > min_views)
    )
    
    articles = conn.execute(stmt).mappings().all()
    
    results = []
    for article in articles:
        length_seconds = (article['reading_time_minutes'] or 7) * 60
        avg_read = article['avg_read_seconds'] or 0
        views = article['views_90d'] or 1
        
        # Completion rate (capped at 100%)
        completion = min(100, (avg_read / length_seconds) * 100) if length_seconds > 0 else 0
        
        # Engagement rate
        engagement = ((article['reactions_90d'] + article['comments_90d']) / views) * 100
        
        # Quality score: 70% completion + 30% engagement (capped at 20%)
        quality_score = (completion * 0.7) + (min(engagement, 20) * 1.5)
        
        results.append({
            'article_id': article['article_id'],
            'title': article['title'],
            'quality_score': quality_score,
            'completion_rate': completion,
            'engagement_rate': engagement,
            'views': views
        })
    
    # Sort by quality score
    results.sort(key=lambda x: x['quality_score'], reverse=True)
    
    return results


# ============================================================================
# SENTIMENT ANALYSIS (nlp_analyzer.py:103-147)
# ============================================================================

def get_unanalyzed_comments(conn, author_username: str = "pascal_cescato_692b7a8a20"):
    """
    Find comments that need sentiment analysis (incremental processing)
    
    Pattern (nlp_analyzer.py:109-116):
        LEFT JOIN comment_insights WHERE insights.comment_id IS NULL
    
    Args:
        conn: SQLAlchemy connection
        author_username: Skip author's own comments
    
    Returns:
        List of comment dicts to analyze
    """
    stmt = (
        select(
            comments.c.comment_id,
            comments.c.article_title,
            comments.c.body_html,
            comments.c.body_text,
        )
        .select_from(
            comments.outerjoin(
                comment_insights,
                comments.c.comment_id == comment_insights.c.comment_id
            )
        )
        .where(
            and_(
                comment_insights.c.comment_id == None,  # Not yet analyzed
                comments.c.author_username != author_username  # Skip author
            )
        )
    )
    
    return conn.execute(stmt).mappings().all()


def classify_sentiment(sentiment_score: float) -> str:
    """
    Apply calibrated thresholds (nlp_analyzer.py:127-132)
    
    Thresholds:
        >= 0.3: Positive
        <= -0.2: Negative
        else: Neutral
    
    Args:
        sentiment_score: VADER compound score (-1.0 to +1.0)
    
    Returns:
        Mood classification string
    """
    if sentiment_score >= 0.3:
        return "🌟 Positif"
    elif sentiment_score <= -0.2:
        return "😟 Négatif"
    else:
        return "😐 Neutre"


def find_unanswered_questions(conn, author_username: str):
    """
    Find reader questions without author replies (nlp_analyzer.py:61-90)
    
    Logic:
        - Comment contains "?"
        - Author is not the writer
        - No reply from author after question timestamp
    
    Returns:
        List of unanswered question dicts
    """
    stmt = text("""
        SELECT 
            q.article_title,
            q.author_username,
            q.body_html,
            q.created_at
        FROM devto_analytics.comments q
        WHERE q.body_html LIKE '%?%'
        AND q.author_username != :author_username
        AND NOT EXISTS (
            SELECT 1 FROM devto_analytics.comments a 
            WHERE a.article_id = q.article_id 
            AND a.author_username = :author_username
            AND a.created_at > q.created_at
        )
        ORDER BY q.created_at DESC
    """)
    
    result = conn.execute(stmt, {"author_username": author_username})
    return result.mappings().all()


# ============================================================================
# ARTICLE PERFORMANCE (dashboard.py)
# ============================================================================

def get_article_restarting(conn, growth_threshold: float = 1.5, min_views: int = 50):
    """
    Find articles with significant traffic resurgence (dashboard.py:320-341)
    
    Thresholds:
        - Growth > 50% (1.5x)
        - Baseline > 50 views
        - Compare last 7 days vs previous 7 days
    
    Returns:
        List of restarting article dicts
    """
    stmt = text("""
        SELECT 
            a1.article_id,
            a1.title,
            a1.views as recent_views,
            a2.views as old_views,
            (a1.views - a2.views) as growth
        FROM (
            SELECT article_id, title, MAX(views) as views
            FROM devto_analytics.article_metrics
            WHERE collected_at >= NOW() - INTERVAL '7 days'
            GROUP BY article_id, title
        ) a1
        JOIN (
            SELECT article_id, MAX(views) as views
            FROM devto_analytics.article_metrics
            WHERE collected_at <= NOW() - INTERVAL '14 days'
            AND collected_at >= NOW() - INTERVAL '21 days'
            GROUP BY article_id
        ) a2 ON a1.article_id = a2.article_id
        WHERE a1.views > a2.views * :growth_threshold
        AND a2.views > :min_views
        ORDER BY growth DESC
        LIMIT 10
    """)
    
    result = conn.execute(stmt, {
        "growth_threshold": growth_threshold,
        "min_views": min_views
    })
    
    return result.mappings().all()


def get_engagement_rate(conn, article_id: int) -> float:
    """
    Calculate engagement rate: (reactions + comments) / views
    
    Returns:
        Engagement percentage (0-100+)
    """
    stmt = (
        select(
            func.max(article_metrics.c.views).label('views'),
            func.max(article_metrics.c.reactions).label('reactions'),
            func.max(article_metrics.c.comments).label('comments'),
        )
        .where(article_metrics.c.article_id == article_id)
    )
    
    row = conn.execute(stmt).mappings().first()
    
    if not row or row['views'] == 0:
        return 0.0
    
    return ((row['reactions'] + row['comments']) / row['views']) * 100


# ============================================================================
# VELOCITY CALCULATION (advanced_analytics.py:98-116)
# ============================================================================

def calculate_velocity(conn, article_id: int, event_time: datetime, 
                       hours_offset: int) -> float:
    """
    Calculate views per hour before/after event
    
    Args:
        conn: SQLAlchemy connection
        article_id: Article to analyze
        event_time: Event timestamp
        hours_offset: +24 (after) or -24 (before)
    
    Returns:
        Velocity (views/hour)
    """
    if hours_offset > 0:
        t_min = event_time
        t_max = event_time + timedelta(hours=hours_offset)
    else:
        t_min = event_time + timedelta(hours=hours_offset)
        t_max = event_time
    
    # Get snapshots in window
    stmt = (
        select(
            article_metrics.c.views,
            article_metrics.c.collected_at
        )
        .where(
            and_(
                article_metrics.c.article_id == article_id,
                article_metrics.c.collected_at.between(t_min, t_max)
            )
        )
        .order_by(article_metrics.c.collected_at)
    )
    
    metrics = conn.execute(stmt).mappings().all()
    
    if len(metrics) < 2:
        return 0.0
    
    v_diff = abs(metrics[-1]['views'] - metrics[0]['views'])
    return v_diff / abs(hours_offset)


# ============================================================================
# CACHE REFRESH
# ============================================================================

def refresh_article_stats_cache(conn):
    """
    Refresh materialized statistics cache for fast dashboard queries
    
    This replaces complex aggregation queries with simple lookups
    Schedule to run hourly via cron/Celery
    """
    from .connection import insert_or_update
    
    # Get all articles with latest metrics
    stmt = (
        select(
            article_metrics.c.article_id,
            func.max(article_metrics.c.views).label('latest_views'),
            func.max(article_metrics.c.reactions).label('latest_reactions'),
            func.max(article_metrics.c.comments).label('latest_comments'),
            func.max(article_metrics.c.collected_at).label('latest_collected_at'),
        )
        .where(article_metrics.c.is_deleted == False)
        .group_by(article_metrics.c.article_id)
    )
    
    articles = conn.execute(stmt).mappings().all()
    
    for article in articles:
        # Calculate quality score
        quality_data = calculate_quality_scores(conn)
        quality_score = next(
            (q['quality_score'] for q in quality_data if q['article_id'] == article['article_id']),
            None
        )
        
        # Calculate engagement rate
        engagement_rate = get_engagement_rate(conn, article['article_id'])
        
        # Upsert cache
        cache_data = {
            'article_id': article['article_id'],
            'latest_views': article['latest_views'],
            'latest_reactions': article['latest_reactions'],
            'latest_comments': article['latest_comments'],
            'latest_collected_at': article['latest_collected_at'],
            'quality_score': quality_score,
            'engagement_rate': engagement_rate,
            'updated_at': datetime.now(),
        }
        
        insert_or_update(
            conn,
            article_stats_cache,
            cache_data,
            conflict_cols=['article_id']
        )
    
    print(f"✅ Refreshed cache for {len(articles)} articles")


# ============================================================================
# VECTOR SIMILARITY SEARCH (PostgreSQL only)
# ============================================================================

def find_similar_articles(conn, article_id: int, limit: int = 5):
    """
    Find semantically similar articles using pgvector
    
    Requires embeddings to be populated in article_content.embedding
    
    Args:
        conn: SQLAlchemy connection
        article_id: Source article
        limit: Number of similar articles
    
    Returns:
        List of similar article dicts with cosine distance
    """
    # Get source article embedding
    source_stmt = (
        select(article_content.c.embedding)
        .where(article_content.c.article_id == article_id)
    )
    
    source = conn.execute(source_stmt).mappings().first()
    if not source or not source['embedding']:
        return []
    
    # Find similar using cosine distance (<=> operator from pgvector)
    stmt = text("""
        SELECT 
            ac.article_id,
            am.title,
            (ac.embedding <=> :embedding::vector) as distance
        FROM devto_analytics.article_content ac
        JOIN devto_analytics.article_metrics am ON ac.article_id = am.article_id
        WHERE ac.article_id != :article_id
        AND ac.embedding IS NOT NULL
        ORDER BY distance
        LIMIT :limit
    """)
    
    result = conn.execute(stmt, {
        "embedding": source['embedding'],
        "article_id": article_id,
        "limit": limit
    })
    
    return result.mappings().all()
