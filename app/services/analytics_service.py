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
            .group_by(article_metrics.c.article_id, article_metrics.c.title, article_metrics.c.published_at)
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
                article_metrics.c.title,
                article_metrics.c.reading_time_minutes,
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
            avg_read = float(row['avg_read_seconds'] or 0)
            completion = min(100, (avg_read / length_sec) * 100) if length_sec > 0 else 0
            
            # Engagement on 90-day window
            views = int(row['views_90d'] or 1)
            reactions = int(row['reactions_90d'] or 0)
            comments = int(row['comments_90d'] or 0)
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
    # CACHE REFRESH
    # ========================================================================
    
    async def refresh_all_stats(self) -> Dict[str, Any]:
        """
        Calculate and cache quality scores and follower attribution for all articles
        
        This method:
        1. Calculates Quality Score using 90-day data from daily_analytics
        2. Computes 7-day and 30-day follower attribution (Share of Voice)
        3. Saves results to article_stats_cache with UPSERT
        
        Quality Score Formula (STRICT):
        - completion_rate = (avg_read_seconds / length_seconds) * 100
        - engagement_rate = ((reactions + comments) / views) * 100
        - quality_score = (completion * 0.7) + (min(engagement, 20) * 1.5)
        
        Returns:
            Dict with refresh statistics
        """
        from app.db.tables import (
            article_metrics as am, 
            daily_analytics as da,
            article_stats_cache
        )
        from sqlalchemy.dialects.postgresql import insert
        
        print("\n" + "="*100)
        print("🔄 REFRESHING ARTICLE STATS CACHE")
        print("="*100)
        
        async with self.engine.connect() as conn:
            # Step 1: Get all articles with their latest metrics and 90-day aggregates
            print("\n📊 Step 1/3: Calculating quality scores...")
            
            # Subquery for 90-day aggregates per article
            da_agg = (
                select(
                    da.c.article_id,
                    func.avg(da.c.average_read_time_seconds).label('avg_read_seconds'),
                    func.max(da.c.page_views).label('views_90d'),
                    func.sum(da.c.reactions_total).label('reactions_90d'),
                    func.sum(da.c.comments_total).label('comments_90d'),
                )
                .group_by(da.c.article_id)
            ).subquery('da_agg')
            
            # Get latest metrics per article
            latest_metrics_subq = (
                select(
                    am.c.article_id,
                    func.max(am.c.collected_at).label('latest_collected_at')
                )
                .group_by(am.c.article_id)
            ).subquery('latest_metrics')
            
            # Main query: Join article_metrics with latest and 90d aggregates
            articles_query = (
                select(
                    am.c.article_id,
                    am.c.title,
                    am.c.reading_time_minutes,
                    am.c.views,
                    am.c.reactions,
                    am.c.comments,
                    am.c.collected_at,
                    da_agg.c.avg_read_seconds,
                    da_agg.c.views_90d,
                    da_agg.c.reactions_90d,
                    da_agg.c.comments_90d,
                )
                .select_from(
                    am
                    .join(
                        latest_metrics_subq,
                        and_(
                            am.c.article_id == latest_metrics_subq.c.article_id,
                            am.c.collected_at == latest_metrics_subq.c.latest_collected_at
                        )
                    )
                    .outerjoin(da_agg, am.c.article_id == da_agg.c.article_id)
                )
            )
            
            result = await conn.execute(articles_query)
            articles = result.mappings().all()
            
            print(f"   Found {len(articles)} articles to process")
            
            # Step 2: Calculate follower attribution (7d and 30d)
            print("\n👥 Step 2/3: Calculating follower attribution...")
            
            attribution_7d = await self.weighted_follower_attribution(hours=168)  # 7 days
            attribution_30d = await self.weighted_follower_attribution(hours=720)  # 30 days
            
            # Create lookup dicts by title (attribution returns title, not article_id)
            attr_7d_map = {
                item['title']: item['attributed_followers']
                for item in attribution_7d.get('attribution', [])
            }
            attr_30d_map = {
                item['title']: item['attributed_followers']
                for item in attribution_30d.get('attribution', [])
            }
            
            print(f"   7-day attribution: {len(attr_7d_map)} articles")
            print(f"   30-day attribution: {len(attr_30d_map)} articles")
            
            # Step 3: Calculate quality scores and prepare UPSERT data
            print("\n💾 Step 3/3: Upserting to article_stats_cache...")
            
            upsert_data = []
            for article in articles:
                # Quality score calculation (same as get_quality_scores)
                length_sec = (article['reading_time_minutes'] or 5) * 60
                avg_read = float(article['avg_read_seconds'] or 0)
                completion = min(100, (avg_read / length_sec) * 100) if length_sec > 0 else 0
                
                # Engagement on 90-day window
                views = int(article['views_90d'] or 1)
                reactions = int(article['reactions_90d'] or 0)
                comments = int(article['comments_90d'] or 0)
                engagement = ((reactions + comments) / views) * 100
                
                # Quality score: 70% completion, 30% engagement (capped at 20%)
                quality_score = (completion * 0.7) + (min(engagement, 20) * 1.5)
                
                # Follower attribution lookup
                title = article['title']
                attributed_7d = attr_7d_map.get(title)
                attributed_30d = attr_30d_map.get(title)
                
                upsert_data.append({
                    'article_id': article['article_id'],
                    'latest_views': article['views'],
                    'latest_reactions': article['reactions'],
                    'latest_comments': article['comments'],
                    'latest_collected_at': article['collected_at'],
                    'quality_score': round(quality_score, 2),
                    'completion_rate': round(completion, 2),
                    'engagement_rate': round(engagement, 2),
                    'attributed_followers_7d': round(attributed_7d, 2) if attributed_7d else None,
                    'attributed_followers_30d': round(attributed_30d, 2) if attributed_30d else None,
                    'updated_at': datetime.now(timezone.utc),
                })
            
            # Perform UPSERT (ON CONFLICT DO UPDATE)
            if upsert_data:
                stmt = insert(article_stats_cache).values(upsert_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=['article_id'],
                    set_={
                        'latest_views': stmt.excluded.latest_views,
                        'latest_reactions': stmt.excluded.latest_reactions,
                        'latest_comments': stmt.excluded.latest_comments,
                        'latest_collected_at': stmt.excluded.latest_collected_at,
                        'quality_score': stmt.excluded.quality_score,
                        'completion_rate': stmt.excluded.completion_rate,
                        'engagement_rate': stmt.excluded.engagement_rate,
                        'attributed_followers_7d': stmt.excluded.attributed_followers_7d,
                        'attributed_followers_30d': stmt.excluded.attributed_followers_30d,
                        'updated_at': stmt.excluded.updated_at,
                    }
                )
                await conn.execute(stmt)
                await conn.commit()
                
                print(f"   ✅ Successfully updated {len(upsert_data)} articles in cache")
            else:
                print("   ⚠️  No data to update")
            
            # Summary statistics
            avg_quality = sum(d['quality_score'] for d in upsert_data) / len(upsert_data) if upsert_data else 0
            articles_with_7d = sum(1 for d in upsert_data if d['attributed_followers_7d'] is not None)
            articles_with_30d = sum(1 for d in upsert_data if d['attributed_followers_30d'] is not None)
            
            print("\n" + "="*100)
            print("✨ REFRESH COMPLETE")
            print("="*100)
            print(f"Total articles: {len(upsert_data)}")
            print(f"Average quality score: {avg_quality:.1f}")
            print(f"Articles with 7d attribution: {articles_with_7d}")
            print(f"Articles with 30d attribution: {articles_with_30d}")
            print("="*100 + "\n")
            
            return {
                'total_articles': len(upsert_data),
                'average_quality_score': round(avg_quality, 2),
                'articles_with_7d_attribution': articles_with_7d,
                'articles_with_30d_attribution': articles_with_30d,
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


    # ========================================================================
    # ADVANCED ANALYTICS (from advanced_analytics.py)
    # ========================================================================
    
    async def article_follower_correlation(
        self,
        tolerance_hours: float = 6.0
    ) -> List[Dict[str, Any]]:
        """
        Calculate follower gain attributed to each article (7-day window)
        
        Migrated from advanced_analytics.py:15-51
        
        Business Logic (STRICT):
        - Use proximity search with 6-hour tolerance (0.25 days)
        - Compare follower count at publication vs 7 days later
        - ORDER BY ABS(EXTRACT(EPOCH...) - EXTRACT(EPOCH...)) for closest match
        
        Args:
            tolerance_hours: Tolerance window for finding closest snapshot (default: 6.0)
        
        Returns:
            List of articles with follower attribution data
        """
        from app.db.tables import article_metrics as am, follower_events
        
        # Get all published articles
        articles_query = (
            select(
                am.c.article_id,
                am.c.title,
                am.c.published_at,
                func.max(am.c.views).label('total_views')
            )
            .where(am.c.published_at.isnot(None))
            .group_by(am.c.article_id, am.c.title, am.c.published_at)
            .order_by(am.c.published_at.desc())
        )
        
        async with self.engine.connect() as conn:
            result = await conn.execute(articles_query)
            articles = result.mappings().all()
            
            correlation_data = []
            
            for article in articles:
                pub_date = article['published_at']
                
                # Start: Publication date (within 6-hour tolerance)
                tolerance_seconds = tolerance_hours * 3600
                start_query = (
                    select(follower_events.c.follower_count)
                    .order_by(
                        func.abs(
                            func.extract('epoch', follower_events.c.collected_at) -
                            func.extract('epoch', pub_date)
                        )
                    )
                    .limit(1)
                )
                start_result = await conn.execute(start_query)
                start_row = start_result.first()
                
                # End: 7 days after publication
                end_date = pub_date + timedelta(days=7)
                end_query = (
                    select(follower_events.c.follower_count)
                    .order_by(
                        func.abs(
                            func.extract('epoch', follower_events.c.collected_at) -
                            func.extract('epoch', end_date)
                        )
                    )
                    .limit(1)
                )
                end_result = await conn.execute(end_query)
                end_row = end_result.first()
                
                if start_row and end_row:
                    gain = end_row[0] - start_row[0]
                    if gain != 0 or start_row[0] > 0:
                        correlation_data.append({
                            'article_id': article['article_id'],
                            'title': article['title'],
                            'published_at': article['published_at'],
                            'follower_gain': gain,
                            'followers_start': start_row[0],
                            'followers_end': end_row[0],
                            'total_views': article['total_views'],
                        })
        
        return correlation_data
    
    async def weighted_follower_attribution(
        self,
        hours: int = 168,
        tolerance_minutes: float = 30.0
    ) -> Dict[str, Any]:
        """
        Attribute new followers proportionally based on traffic gain (Share of Voice)
        
        Migrated from advanced_analytics.py:118-227
        
        Business Logic (STRICT):
        - Find closest follower snapshots at start/end of period
        - Calculate total follower gain
        - Calculate traffic gain per article
        - Attribute followers proportionally: (article_views / total_views) * total_followers
        
        PostgreSQL Conversion:
        - REPLACE: strftime('%s', ...) with EXTRACT(EPOCH FROM ...)
        - Proximity search: ORDER BY ABS(EXTRACT(EPOCH ...) - EXTRACT(EPOCH ...))
        
        Args:
            hours: Analysis period in hours (default: 168 = 7 days)
            tolerance_minutes: Tolerance for snapshot proximity (default: 30)
        
        Returns:
            Dict with attribution data and metadata
        """
        from app.db.tables import follower_events, article_metrics as am
        
        # 1. Define analysis period
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        
        async with self.engine.connect() as conn:
            # 2. Find closest follower snapshots
            # Start snapshot (closest to start_time)
            start_query = (
                select(
                    follower_events.c.follower_count,
                    follower_events.c.collected_at
                )
                .order_by(
                    func.abs(
                        func.extract('epoch', follower_events.c.collected_at) -
                        func.extract('epoch', start_time)
                    )
                )
                .limit(1)
            )
            start_result = await conn.execute(start_query)
            start_snapshot = start_result.mappings().first()
            
            # End snapshot (closest to end_time)
            end_query = (
                select(
                    follower_events.c.follower_count,
                    follower_events.c.collected_at
                )
                .order_by(
                    func.abs(
                        func.extract('epoch', follower_events.c.collected_at) -
                        func.extract('epoch', end_time)
                    )
                )
                .limit(1)
            )
            end_result = await conn.execute(end_query)
            end_snapshot = end_result.mappings().first()
            
            if not start_snapshot or not end_snapshot:
                return {
                    'error': 'Need at least two follower snapshots',
                    'total_gain': 0,
                    'attribution': []
                }
            
            # Check if same snapshot
            if start_snapshot['collected_at'] == end_snapshot['collected_at']:
                return {
                    'error': 'Need two different snapshots',
                    'total_gain': 0,
                    'attribution': []
                }
            
            # Calculate actual interval
            actual_interval = end_snapshot['collected_at'] - start_snapshot['collected_at']
            actual_hours = actual_interval.total_seconds() / 3600
            
            # Calculate total follower gain
            total_gain = end_snapshot['follower_count'] - start_snapshot['follower_count']
            
            if total_gain <= 0:
                return {
                    'total_gain': total_gain,
                    'actual_hours': actual_hours,
                    'attribution': []
                }
            
            # 3. Calculate traffic gain per article
            # Get distinct articles
            articles_query = (
                select(
                    am.c.article_id,
                    am.c.title,
                )
                .distinct()
            )
            articles_result = await conn.execute(articles_query)
            articles = articles_result.mappings().all()
            
            attribution_data = []
            global_traffic_gain = 0
            
            for article in articles:
                # Views at start (proximity search)
                v_start_query = (
                    select(am.c.views)
                    .where(am.c.article_id == article['article_id'])
                    .order_by(
                        func.abs(
                            func.extract('epoch', am.c.collected_at) -
                            func.extract('epoch', start_time)
                        )
                    )
                    .limit(1)
                )
                v_start_result = await conn.execute(v_start_query)
                v_start_row = v_start_result.first()
                
                # Views at end (proximity search)
                v_end_query = (
                    select(am.c.views)
                    .where(am.c.article_id == article['article_id'])
                    .order_by(
                        func.abs(
                            func.extract('epoch', am.c.collected_at) -
                            func.extract('epoch', end_time)
                        )
                    )
                    .limit(1)
                )
                v_end_result = await conn.execute(v_end_query)
                v_end_row = v_end_result.first()
                
                if v_start_row and v_end_row:
                    views_gain = v_end_row[0] - v_start_row[0]
                    if views_gain > 0:
                        attribution_data.append({
                            'title': article['title'],
                            'views_gain': views_gain
                        })
                        global_traffic_gain += views_gain
            
            if global_traffic_gain == 0:
                return {
                    'error': 'No traffic detected in period',
                    'total_gain': total_gain,
                    'actual_hours': actual_hours,
                    'attribution': []
                }
            
            # 4. Calculate proportional attribution
            # Sort by views gain (descending)
            attribution_data.sort(key=lambda x: x['views_gain'], reverse=True)
            
            for item in attribution_data:
                share = item['views_gain'] / global_traffic_gain
                attributed_followers = share * total_gain
                item['traffic_share'] = share
                item['attributed_followers'] = attributed_followers
            
            return {
                'total_gain': total_gain,
                'global_traffic_gain': global_traffic_gain,
                'actual_hours': actual_hours,
                'start_time': start_snapshot['collected_at'],
                'end_time': end_snapshot['collected_at'],
                'attribution': attribution_data
            }
    
    async def engagement_evolution(
        self,
        article_id: int,
        hours_before: int = 24,
        hours_after: int = 24
    ) -> Dict[str, Any]:
        """
        Calculate velocity (views/hour) around a specific event
        
        Migrated from advanced_analytics.py:98-116
        
        Business Logic:
        - Calculate views/hour using: EXTRACT(EPOCH FROM (ts2 - ts1)) / 3600
        - Compare velocity before and after milestone events
        
        Args:
            article_id: Article to analyze
            hours_before: Hours before event (default: 24)
            hours_after: Hours after event (default: 24)
        
        Returns:
            Dict with velocity data
        """
        from app.db.tables import article_metrics as am, milestone_events
        
        # Get milestone events for this article
        events_query = (
            select(
                milestone_events.c.event_type,
                milestone_events.c.occurred_at,
                milestone_events.c.velocity_before,
                milestone_events.c.velocity_after
            )
            .where(milestone_events.c.article_id == article_id)
            .order_by(milestone_events.c.occurred_at.desc())
        )
        
        async with self.engine.connect() as conn:
            result = await conn.execute(events_query)
            events = result.mappings().all()
            
            evolution_data = []
            
            for event in events:
                event_time = event['occurred_at']
                
                # Calculate velocity before (if not stored)
                if event['velocity_before'] is None:
                    t_before_start = event_time - timedelta(hours=hours_before)
                    
                    metrics_query = (
                        select(am.c.views, am.c.collected_at)
                        .where(
                            and_(
                                am.c.article_id == article_id,
                                am.c.collected_at.between(t_before_start, event_time)
                            )
                        )
                        .order_by(am.c.collected_at)
                    )
                    
                    metrics_result = await conn.execute(metrics_query)
                    metrics = metrics_result.mappings().all()
                    
                    if len(metrics) >= 2:
                        v_diff = metrics[-1]['views'] - metrics[0]['views']
                        velocity_before = v_diff / hours_before
                    else:
                        velocity_before = 0.0
                else:
                    velocity_before = event['velocity_before']
                
                # Calculate velocity after (if not stored)
                if event['velocity_after'] is None:
                    t_after_end = event_time + timedelta(hours=hours_after)
                    
                    metrics_query = (
                        select(am.c.views, am.c.collected_at)
                        .where(
                            and_(
                                am.c.article_id == article_id,
                                am.c.collected_at.between(event_time, t_after_end)
                            )
                        )
                        .order_by(am.c.collected_at)
                    )
                    
                    metrics_result = await conn.execute(metrics_query)
                    metrics = metrics_result.mappings().all()
                    
                    if len(metrics) >= 2:
                        v_diff = metrics[-1]['views'] - metrics[0]['views']
                        velocity_after = v_diff / hours_after
                    else:
                        velocity_after = 0.0
                else:
                    velocity_after = event['velocity_after']
                
                # Calculate impact
                if velocity_before > 0:
                    impact = ((velocity_after - velocity_before) / velocity_before) * 100
                elif velocity_after > 0:
                    impact = 100.0
                else:
                    impact = 0.0
                
                evolution_data.append({
                    'event_type': event['event_type'],
                    'occurred_at': event['occurred_at'],
                    'velocity_before': velocity_before,
                    'velocity_after': velocity_after,
                    'impact_percent': impact
                })
            
            return {
                'article_id': article_id,
                'events': evolution_data
            }
    
    async def get_overview(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Get global trends with delta compared to previous period
        
        Returns metrics for current period vs previous period
        
        Args:
            days: Period length in days (default: 7)
        
        Returns:
            Dict with current metrics and deltas
        """
        from app.db.tables import article_metrics as am
        
        current_end = datetime.now(timezone.utc)
        current_start = current_end - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)
        
        async with self.engine.connect() as conn:
            # Current period metrics
            current_query = (
                select(
                    func.sum(am.c.views).label('total_views'),
                    func.sum(am.c.reactions).label('total_reactions'),
                    func.sum(am.c.comments).label('total_comments'),
                )
                .where(am.c.collected_at.between(current_start, current_end))
            )
            current_result = await conn.execute(current_query)
            current = current_result.mappings().first()
            
            # Previous period metrics
            previous_query = (
                select(
                    func.sum(am.c.views).label('total_views'),
                    func.sum(am.c.reactions).label('total_reactions'),
                    func.sum(am.c.comments).label('total_comments'),
                )
                .where(am.c.collected_at.between(previous_start, current_start))
            )
            previous_result = await conn.execute(previous_query)
            previous = previous_result.mappings().first()
            
            # Calculate deltas
            views_delta = current['total_views'] - previous['total_views'] if previous['total_views'] else 0
            reactions_delta = current['total_reactions'] - previous['total_reactions'] if previous['total_reactions'] else 0
            comments_delta = current['total_comments'] - previous['total_comments'] if previous['total_comments'] else 0
            
            return {
                'period_days': days,
                'current': {
                    'views': current['total_views'] or 0,
                    'reactions': current['total_reactions'] or 0,
                    'comments': current['total_comments'] or 0,
                },
                'previous': {
                    'views': previous['total_views'] or 0,
                    'reactions': previous['total_reactions'] or 0,
                    'comments': previous['total_comments'] or 0,
                },
                'delta': {
                    'views': views_delta,
                    'reactions': reactions_delta,
                    'comments': comments_delta,
                },
                'delta_percent': {
                    'views': (views_delta / previous['total_views'] * 100) if previous['total_views'] else 0,
                    'reactions': (reactions_delta / previous['total_reactions'] * 100) if previous['total_reactions'] else 0,
                    'comments': (comments_delta / previous['total_comments'] * 100) if previous['total_comments'] else 0,
                }
            }
    
    async def best_publishing_times(self) -> Dict[str, Any]:
        """
        Find best days and hours for publishing based on performance
        
        Uses PostgreSQL date/time extraction:
        - func.extract('dow', published_at) for day of week (0=Sunday, 6=Saturday)
        - func.extract('hour', published_at) for hour of day (0-23)
        
        Returns:
            Dict with best days and hours ranked by performance
        """
        from app.db.tables import article_metrics as am
        
        async with self.engine.connect() as conn:
            # Best day of week
            dow_query = (
                select(
                    func.extract('dow', am.c.published_at).label('day_of_week'),
                    func.count(func.distinct(am.c.article_id)).label('article_count'),
                    func.avg(am.c.views).label('avg_views'),
                    func.avg(am.c.reactions).label('avg_reactions'),
                )
                .where(am.c.published_at.isnot(None))
                .group_by(func.extract('dow', am.c.published_at))
                .order_by(func.avg(am.c.views).desc())
            )
            dow_result = await conn.execute(dow_query)
            dow_data = dow_result.mappings().all()
            
            # Best hour of day
            hour_query = (
                select(
                    func.extract('hour', am.c.published_at).label('hour'),
                    func.count(func.distinct(am.c.article_id)).label('article_count'),
                    func.avg(am.c.views).label('avg_views'),
                    func.avg(am.c.reactions).label('avg_reactions'),
                )
                .where(am.c.published_at.isnot(None))
                .group_by(func.extract('hour', am.c.published_at))
                .order_by(func.avg(am.c.views).desc())
            )
            hour_result = await conn.execute(hour_query)
            hour_data = hour_result.mappings().all()
            
            # Map day numbers to names
            day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
            
            return {
                'best_days': [
                    {
                        'day_of_week': int(row['day_of_week']),
                        'day_name': day_names[int(row['day_of_week'])],
                        'article_count': row['article_count'],
                        'avg_views': float(row['avg_views']) if row['avg_views'] else 0,
                        'avg_reactions': float(row['avg_reactions']) if row['avg_reactions'] else 0,
                    }
                    for row in dow_data
                ],
                'best_hours': [
                    {
                        'hour': int(row['hour']),
                        'article_count': row['article_count'],
                        'avg_views': float(row['avg_views']) if row['avg_views'] else 0,
                        'avg_reactions': float(row['avg_reactions']) if row['avg_reactions'] else 0,
                    }
                    for row in hour_data
                ]
            }


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
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--refresh':
            # Refresh article stats cache
            await service.refresh_all_stats()
        elif sys.argv[1].startswith('--article='):
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
            print("Usage:")
            print("  --refresh              Refresh article stats cache")
            print("  --article=<id>         Show daily breakdown for article")
            print("  --overview (default)   Show quality dashboard")
    else:
        # Show full dashboard (default)
        await service.show_quality_dashboard()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
