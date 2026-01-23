"""
Analytics Service - PostgreSQL-First Quality and Traffic Analysis

Refactored from traffic_analytics.py (formerly quality_analytics.py)
- Converts all SQLite julianday() logic to PostgreSQL interval and date math
- Uses SQLAlchemy Core select() statements instead of raw SQL
- Preserves Quality Score calculation: (completion × 0.7) + (LEAST(engagement, 20) × 1.5)
- Maintains 90-day data window and business logic
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func, and_, or_, cast, Integer, Float, Text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.sql import text

from app.db.tables import (
    article_metrics,
    daily_analytics,
)


class AnalyticsService:
    """
    Modern analytics service for quality and traffic analysis
    
    Replaces QualityAnalytics from traffic_analytics.py
    All queries use SQLAlchemy Core with PostgreSQL-specific functions
    """
    
    def __init__(self, engine: Optional[AsyncEngine] = None, db_url: Optional[str] = None):
        """
        Initialize analytics service
        
        Args:
            engine: Existing AsyncEngine (preferred)
            db_url: Database URL if engine not provided
        """
        if engine:
            self.engine = engine
        elif db_url:
            self.engine = create_async_engine(
                db_url,
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )
        else:
            raise ValueError("Either engine or db_url must be provided")
    
    # ========================================================================
    # READ TIME ANALYSIS
    # ========================================================================
    
    async def get_read_time_analysis(
        self,
        min_views: int = 20,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Analyze average read times per article
        
        Replaces: show_read_time_analysis() from traffic_analytics.py
        
        PostgreSQL conversions:
        - julianday('now') - julianday(published_at) → NOW() - published_at (returns INTERVAL)
        - Extract days from interval: EXTRACT(EPOCH FROM interval) / 86400
        
        Returns: List of articles with read time metrics
        """
        # Subquery for aggregated daily analytics
        da_agg = (
            select(
                daily_analytics.c.article_id,
                func.avg(daily_analytics.c.average_read_time_seconds).label('avg_read_seconds'),
                func.max(daily_analytics.c.page_views).label('total_views'),
                func.max(daily_analytics.c.total_read_time_seconds).label('total_read_seconds'),
                func.count(func.distinct(daily_analytics.c.date)).label('days_with_data'),
            )
            .where(daily_analytics.c.page_views > 0)
            .group_by(daily_analytics.c.article_id)
            .alias('da_agg')
        )
        
        # Main query joining with article_metrics
        # PostgreSQL: age(NOW(), published_at) returns INTERVAL
        # EXTRACT(EPOCH FROM interval) / 86400 converts to days
        query = (
            select(
                da_agg.c.article_id,
                article_metrics.c.title,
                article_metrics.c.reading_time_minutes,
                article_metrics.c.published_at,
                # Age in days: NOW() - published_at converted to days
                (
                    func.extract('epoch', func.now() - article_metrics.c.published_at) / 86400
                ).label('age_days'),
                da_agg.c.avg_read_seconds,
                da_agg.c.total_views,
                da_agg.c.total_read_seconds,
                da_agg.c.days_with_data,
            )
            .select_from(
                da_agg.join(
                    article_metrics,
                    da_agg.c.article_id == article_metrics.c.article_id
                )
            )
            .where(da_agg.c.total_views > min_views)
            .order_by(da_agg.c.avg_read_seconds.desc())
            .limit(limit)
        )
        
        async with self.engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        
        # Calculate completion percentage
        articles = []
        for row in rows:
            length_seconds = (row['reading_time_minutes'] or 0) * 60
            avg_read = row['avg_read_seconds'] or 0
            completion = min(100, (avg_read / length_seconds) * 100) if length_seconds > 0 else 0
            total_hours = (row['total_read_seconds'] or 0) / 3600
            
            articles.append({
                'article_id': row['article_id'],
                'title': row['title'],
                'reading_time_minutes': row['reading_time_minutes'],
                'published_at': row['published_at'],
                'age_days': int(row['age_days']) if row['age_days'] else 0,
                'avg_read_seconds': int(avg_read),
                'total_views': row['total_views'],
                'total_hours': round(total_hours, 1),
                'completion_percent': round(completion, 1),
                'days_with_data': row['days_with_data'],
            })
        
        return articles
    
    # ========================================================================
    # REACTION BREAKDOWN ANALYSIS
    # ========================================================================
    
    async def get_reaction_breakdown(
        self,
        min_reactions: int = 5,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Analyze reaction types with lifetime vs 90-day breakdown
        
        Replaces: show_reaction_breakdown() from traffic_analytics.py
        
        PostgreSQL conversions:
        - julianday('now') - julianday(published_at) → NOW() - published_at
        - date >= date('now', '-30 days') → date >= CURRENT_DATE - INTERVAL '30 days'
        
        Returns: List of articles with reaction breakdown
        """
        # Subqueries for reaction sums (90-day window)
        likes_subq = (
            select(func.sum(daily_analytics.c.reactions_like))
            .where(
                and_(
                    daily_analytics.c.article_id == article_metrics.c.article_id,
                    daily_analytics.c.date >= func.date(article_metrics.c.published_at)
                )
            )
            .scalar_subquery()
        )
        
        unicorns_subq = (
            select(func.sum(daily_analytics.c.reactions_unicorn))
            .where(
                and_(
                    daily_analytics.c.article_id == article_metrics.c.article_id,
                    daily_analytics.c.date >= func.date(article_metrics.c.published_at)
                )
            )
            .scalar_subquery()
        )
        
        bookmarks_subq = (
            select(func.sum(daily_analytics.c.reactions_readinglist))
            .where(
                and_(
                    daily_analytics.c.article_id == article_metrics.c.article_id,
                    daily_analytics.c.date >= func.date(article_metrics.c.published_at)
                )
            )
            .scalar_subquery()
        )
        
        # Main query
        query = (
            select(
                article_metrics.c.article_id,
                article_metrics.c.title,
                article_metrics.c.published_at,
                # Age in days
                (
                    func.extract('epoch', func.now() - article_metrics.c.published_at) / 86400
                ).label('age_days'),
                # Lifetime total reactions (MAX to deduplicate snapshots)
                func.max(article_metrics.c.reactions).label('total_reactions_lifetime'),
                # Breakdown sums (90-day window)
                likes_subq.label('likes_sum'),
                unicorns_subq.label('unicorns_sum'),
                bookmarks_subq.label('bookmarks_sum'),
            )
            .where(article_metrics.c.reactions > min_reactions)
            .group_by(article_metrics.c.article_id)
            .order_by(func.max(article_metrics.c.reactions).desc())
            .limit(limit)
        )
        
        async with self.engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        
        # Calculate gaps
        articles = []
        for row in rows:
            likes = row['likes_sum'] or 0
            unicorns = row['unicorns_sum'] or 0
            bookmarks = row['bookmarks_sum'] or 0
            breakdown_sum = likes + unicorns + bookmarks
            gap = row['total_reactions_lifetime'] - breakdown_sum
            
            articles.append({
                'article_id': row['article_id'],
                'title': row['title'],
                'published_at': row['published_at'],
                'age_days': int(row['age_days']) if row['age_days'] else 0,
                'total_reactions_lifetime': row['total_reactions_lifetime'],
                'likes': likes,
                'unicorns': unicorns,
                'bookmarks': bookmarks,
                'breakdown_sum': breakdown_sum,
                'gap': gap,
            })
        
        return articles
    
    # ========================================================================
    # QUALITY SCORES
    # ========================================================================
    
    async def get_quality_scores(
        self,
        min_views: int = 20,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Calculate quality scores based on read completion and engagement
        
        Replaces: show_quality_scores() from traffic_analytics.py
        
        Formula (preserved from original):
        - Completion %: (avg_read_time / reading_time_minutes * 60) * 100
        - Engagement %: ((reactions + comments) / views) * 100
        - Quality Score: (completion * 0.7) + (min(engagement, 20) * 1.5)
        
        Returns: List of articles sorted by quality score
        """
        # Aggregate daily analytics per article
        da_agg = (
            select(
                daily_analytics.c.article_id,
                func.avg(daily_analytics.c.average_read_time_seconds).label('avg_read_seconds'),
                func.max(daily_analytics.c.page_views).label('views_90d'),
                func.sum(daily_analytics.c.reactions_total).label('reactions_90d'),
                func.sum(daily_analytics.c.comments_total).label('comments_90d'),
            )
            .group_by(daily_analytics.c.article_id)
            .alias('da_agg')
        )
        
        # Join with article_metrics
        query = (
            select(
                article_metrics.c.article_id,
                article_metrics.c.title,
                article_metrics.c.reading_time_minutes,
                da_agg.c.avg_read_seconds,
                da_agg.c.views_90d,
                da_agg.c.reactions_90d,
                da_agg.c.comments_90d,
            )
            .select_from(
                article_metrics.join(
                    da_agg,
                    article_metrics.c.article_id == da_agg.c.article_id
                )
            )
            .where(da_agg.c.views_90d > min_views)
            .group_by(
                article_metrics.c.article_id,
                da_agg.c.avg_read_seconds,
                da_agg.c.views_90d,
                da_agg.c.reactions_90d,
                da_agg.c.comments_90d,
            )
        )
        
        async with self.engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        
        # Calculate quality scores
        scored = []
        for row in rows:
            length_sec = (row['reading_time_minutes'] or 5) * 60
            avg_read = row['avg_read_seconds'] or 0
            completion = min(100, (avg_read / length_sec) * 100) if length_sec > 0 else 0
            
            # Engagement on 90-day window
            views = row['views_90d'] or 1
            reactions = row['reactions_90d'] or 0
            comments = row['comments_90d'] or 0
            engagement = ((reactions + comments) / views) * 100
            
            # Quality score: 70% completion, 30% engagement (capped at 20%)
            score = (completion * 0.7) + (min(engagement, 20) * 1.5)
            
            scored.append({
                'article_id': row['article_id'],
                'title': row['title'],
                'reading_time_minutes': row['reading_time_minutes'],
                'views_90d': views,
                'reactions_90d': reactions,
                'comments_90d': comments,
                'completion_percent': round(completion, 1),
                'engagement_percent': round(engagement, 1),
                'quality_score': round(score, 1),
            })
        
        # Sort by quality score descending
        scored.sort(key=lambda x: x['quality_score'], reverse=True)
        
        if limit:
            scored = scored[:limit]
        
        return scored
    
    # ========================================================================
    # LONG-TAIL CHAMPIONS
    # ========================================================================
    
    async def get_long_tail_champions(
        self,
        days_old: int = 30,
        days_window: int = 30,
        min_views: int = 20,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Identify articles with stable long-term performance
        
        Replaces: show_long_tail_champions() from traffic_analytics.py
        
        PostgreSQL conversions:
        - date('now', '-30 days') → CURRENT_DATE - INTERVAL '30 days'
        - julianday('now') - julianday(published_at) → age calculation
        
        Args:
            days_old: Minimum article age in days (default: 30)
            days_window: Window for recent views (default: 30)
            min_views: Minimum views in window (default: 20)
            limit: Max results to return (default: 10)
        
        Returns: List of long-tail champion articles
        """
        # Subquery: aggregate views per article in time window
        cutoff_date = func.current_date() - text(f"INTERVAL '{days_window} days'")
        
        stats_subq = (
            select(
                daily_analytics.c.article_id,
                func.sum(daily_analytics.c.page_views).label('views_window')
            )
            .where(daily_analytics.c.date >= cutoff_date)
            .group_by(daily_analytics.c.article_id)
            .alias('stats')
        )
        
        # Distinct article info (deduplicate snapshots)
        article_subq = (
            select(
                article_metrics.c.article_id,
                article_metrics.c.title,
                article_metrics.c.published_at,
            )
            .distinct()
            .alias('am')
        )
        
        # Main query
        query = (
            select(
                article_subq.c.article_id,
                article_subq.c.title,
                article_subq.c.published_at,
                # Age in days
                (
                    func.extract('epoch', func.now() - article_subq.c.published_at) / 86400
                ).label('age_days'),
                stats_subq.c.views_window,
            )
            .select_from(
                stats_subq.join(
                    article_subq,
                    stats_subq.c.article_id == article_subq.c.article_id
                )
            )
            .where(
                and_(
                    # Published before the window (old enough)
                    article_subq.c.published_at < func.current_date() - text(f"INTERVAL '{days_old} days'"),
                    # Has sufficient views
                    stats_subq.c.views_window > min_views
                )
            )
            .order_by(stats_subq.c.views_window.desc())
            .limit(limit)
        )
        
        async with self.engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        
        champions = []
        for row in rows:
            champions.append({
                'article_id': row['article_id'],
                'title': row['title'],
                'published_at': row['published_at'],
                'age_days': int(row['age_days']) if row['age_days'] else 0,
                'views_window': row['views_window'],
                'days_window': days_window,
            })
        
        return champions
    
    # ========================================================================
    # ARTICLE DAILY BREAKDOWN
    # ========================================================================
    
    async def get_article_daily_breakdown(
        self,
        article_id: int,
        days: int = 14
    ) -> Dict[str, Any]:
        """
        Get daily breakdown for a specific article
        
        Replaces: analyze_article_daily() from traffic_analytics.py
        
        Args:
            article_id: DEV.to article ID
            days: Number of days to retrieve (default: 14)
        
        Returns: Dict with article info and daily data
        """
        # Get article title
        title_query = select(article_metrics.c.title).where(
            article_metrics.c.article_id == article_id
        ).limit(1)
        
        # Get daily data
        daily_query = (
            select(
                daily_analytics.c.date,
                daily_analytics.c.page_views,
                daily_analytics.c.average_read_time_seconds,
                daily_analytics.c.reactions_total,
                daily_analytics.c.comments_total,
            )
            .where(daily_analytics.c.article_id == article_id)
            .order_by(daily_analytics.c.date.desc())
            .limit(days)
        )
        
        async with self.engine.connect() as conn:
            # Get title
            title_result = await conn.execute(title_query)
            title_row = title_result.first()
            if not title_row:
                return None
            
            # Get daily data
            daily_result = await conn.execute(daily_query)
            daily_rows = daily_result.mappings().all()
        
        return {
            'article_id': article_id,
            'title': title_row[0],
            'daily_data': [
                {
                    'date': str(row['date']),
                    'page_views': row['page_views'],
                    'avg_read_seconds': row['average_read_time_seconds'],
                    'reactions': row['reactions_total'],
                    'comments': row['comments_total'],
                }
                for row in daily_rows
            ]
        }
    
    # ========================================================================
    # DASHBOARD VIEWS
    # ========================================================================
    
    async def get_quality_dashboard(self) -> Dict[str, Any]:
        """
        Get complete quality dashboard data
        
        Replaces: show_quality_dashboard() from traffic_analytics.py
        
        Returns: Dict with all analytics sections
        """
        print("\n" + "="*100)
        print("📊 QUALITY ANALYTICS DASHBOARD")
        print("="*100)
        
        dashboard = {
            'read_time_analysis': await self.get_read_time_analysis(limit=10),
            'reaction_breakdown': await self.get_reaction_breakdown(limit=10),
            'quality_scores': await self.get_quality_scores(limit=10),
            'long_tail_champions': await self.get_long_tail_champions(limit=10),
        }
        
        return dashboard
    
    def print_read_time_analysis(self, articles: List[Dict[str, Any]]):
        """Pretty print read time analysis"""
        print(f"\n\n📖 READ TIME ANALYSIS (Top {len(articles)})")
        print("-" * 100)
        print(f"{'Title':<50} {'Length':>8} {'Avg Read':>10} {'Completion':>12} {'Total Hours':>12}")
        print("-" * 100)
        
        for article in articles:
            title = (article['title'][:47] + "...") if len(article['title']) > 50 else article['title']
            print(f"{title:<50} {article['reading_time_minutes']:>7}m "
                  f"{article['avg_read_seconds']:>8}s "
                  f"{article['completion_percent']:>10.1f}% "
                  f"{article['total_hours']:>11.1f}h")
        
        print("\n💡 Note: Read time data covers last 90 days only")
    
    def print_reaction_breakdown(self, articles: List[Dict[str, Any]]):
        """Pretty print reaction breakdown"""
        print(f"\n\n❤️ REACTION BREAKDOWN (Top {len(articles)})")
        print("-" * 120)
        print(f"{'Title':<45} {'Age':>6} {'Lifetime':>10} │ {'Likes':>7} {'🦄':>5} {'📖':>5} {'Sum':>8} {'Gap':>5}")
        print("-" * 120)
        
        for article in articles:
            title = (article['title'][:42] + "...") if len(article['title']) > 45 else article['title']
            gap = article['gap']
            gap_str = f"{gap:+d}" if gap != 0 else "="
            
            print(f"{title:<45} {article['age_days']:>5}d {article['total_reactions_lifetime']:>10} │ "
                  f"{article['likes']:>7} {article['unicorns']:>5} {article['bookmarks']:>5} "
                  f"{article['breakdown_sum']:>8} {gap_str:>5}")
        
        print("-" * 120)
        print("💡 Gap > 0 : Old reactions (>90d) where type (Like/Unicorn) is lost.")
        print("   Gap < 0 : Reactions removed by users (history preserved vs current state).")
    
    def print_quality_scores(self, articles: List[Dict[str, Any]]):
        """Pretty print quality scores"""
        print(f"\n\n⭐ QUALITY SCORES (90-day performance)")
        print("-" * 100)
        print(f"{'Title':<50} {'Quality':>9} {'Read %':>8} {'Engage %':>10}")
        print("-" * 100)
        
        for article in articles:
            title = (article['title'][:47] + "...") if len(article['title']) > 50 else article['title']
            print(f"{title:<50} {article['quality_score']:>8.1f} "
                  f"{article['completion_percent']:>7.1f}% "
                  f"{article['engagement_percent']:>9.1f}%")
    
    def print_long_tail_champions(self, articles: List[Dict[str, Any]]):
        """Pretty print long-tail champions"""
        print(f"\n\n🌟 LONG-TAIL CHAMPIONS (Real views / {articles[0]['days_window'] if articles else 30}d)")
        print("-" * 80)
        
        for article in articles:
            title = (article['title'][:50] + "...") if len(article['title']) > 53 else article['title']
            print(f"{title:<53} {article['age_days']:>5}d {article['views_window']:>10} views/{article['days_window']}d")
    
    async def show_quality_dashboard(self):
        """
        Display complete quality dashboard (console output)
        
        Replaces: show_quality_dashboard() from traffic_analytics.py
        """
        dashboard = await self.get_quality_dashboard()
        
        self.print_read_time_analysis(dashboard['read_time_analysis'])
        self.print_reaction_breakdown(dashboard['reaction_breakdown'])
        self.print_quality_scores(dashboard['quality_scores'])
        self.print_long_tail_champions(dashboard['long_tail_champions'])
        
        print("\n" + "="*100)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def create_analytics_service(engine: Optional[AsyncEngine] = None) -> AnalyticsService:
    """
    Create AnalyticsService instance
    
    Args:
        engine: Optional existing AsyncEngine
    
    Returns:
        Initialized AnalyticsService
    """
    if engine:
        return AnalyticsService(engine=engine)
    
    # Create engine from environment variables
    import os
    
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'devto_analytics')
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD')
    
    if not user or not password:
        raise ValueError("Missing required environment variables: POSTGRES_USER and POSTGRES_PASSWORD")
    
    db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return AnalyticsService(db_url=db_url)


async def main():
    """CLI entry point for testing"""
    import sys
    
    service = await create_analytics_service()
    
    if len(sys.argv) > 1 and sys.argv[1].startswith('--article='):
        # Show daily breakdown for specific article
        article_id = int(sys.argv[1].split('=')[1])
        breakdown = await service.get_article_daily_breakdown(article_id)
        
        if breakdown:
            print(f"\n📊 DAILY BREAKDOWN: {breakdown['title']}")
            print(f"{'Date':<12} {'Views':>7} {'Read(s)':>9} {'Reactions':>10} {'Comments':>10}")
            for day in breakdown['daily_data']:
                print(f"{day['date']:<12} {day['page_views']:>7} "
                      f"{day['avg_read_seconds']:>9} {day['reactions']:>10} {day['comments']:>10}")
        else:
            print(f"❌ Article {article_id} not found")
    else:
        # Show full dashboard
        await service.show_quality_dashboard()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
