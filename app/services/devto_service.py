"""
DEV.to API Service - Modern Async PostgreSQL-First Architecture

Refactored from devto_tracker.py and core/database.py
- Uses httpx.AsyncClient for all API calls (replaces requests)
- Uses SQLAlchemy Core with AsyncEngine for database operations
- Implements proper tag/tag_list conversions for PostgreSQL ARRAY type
- Maintains all business logic patterns from original implementation
"""

import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from sqlalchemy import select, insert, update, func
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, AsyncConnection
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.tables import (
    article_metrics,
    follower_events,
    comments,
    daily_analytics,
    referrers,
    article_history,
    milestone_events,
)


class DevToService:
    """
    Modern async service for DEV.to data collection
    
    Replaces DevToTracker class from devto_tracker.py
    Uses async/await pattern throughout
    """
    
    def __init__(
        self,
        api_key: str,
        db_url: Optional[str] = None,
        rate_limit_delay: float = 0.5
    ):
        """
        Initialize DEV.to service
        
        Args:
            api_key: DEV.to API key for authentication
            db_url: PostgreSQL connection URL (uses env vars if not provided)
            rate_limit_delay: Seconds to wait between API calls (default: 0.5)
        """
        self.api_key = api_key
        self.base_url = "https://dev.to/api"
        self.rate_limit_delay = rate_limit_delay
        
        # Async HTTP client (replaces requests.get)
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # Async database engine
        if db_url is None:
            db_url = self._get_async_database_url()
        self.engine: AsyncEngine = create_async_engine(
            db_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
    
    def _get_async_database_url(self) -> str:
        """Construct async PostgreSQL URL from environment variables"""
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        database = os.getenv('POSTGRES_DB', 'devto_analytics')
        user = os.getenv('POSTGRES_USER')
        password = os.getenv('POSTGRES_PASSWORD')
        
        if not user or not password:
            raise ValueError(
                "Missing required environment variables: POSTGRES_USER and POSTGRES_PASSWORD"
            )
        
        # asyncpg driver for async operations
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.http_client = httpx.AsyncClient(
            headers={"api-key": self.api_key},
            timeout=30.0,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.http_client:
            await self.http_client.aclose()
        await self.engine.dispose()
    
    # ========================================================================
    # API METHODS (replaces requests.get with httpx.AsyncClient)
    # ========================================================================
    
    async def fetch_articles(self) -> List[Dict[str, Any]]:
        """
        Fetch all articles from DEV.to API
        
        Replaces: fetch_api_articles() from devto_tracker.py
        Returns: List of article dictionaries
        """
        if not self.http_client:
            raise RuntimeError("Service not initialized. Use 'async with DevToService(...)'")
        
        url = f"{self.base_url}/articles/me/all"
        response = await self.http_client.get(url, params={"per_page": 1000})
        response.raise_for_status()
        return response.json()
    
    async def fetch_followers(self) -> List[Dict[str, Any]]:
        """
        Fetch all followers with pagination
        
        Replaces: _collect_followers() from devto_tracker.py (API part)
        Returns: List of follower dictionaries
        """
        if not self.http_client:
            raise RuntimeError("Service not initialized")
        
        all_followers = []
        page = 1
        
        while True:
            response = await self.http_client.get(
                f"{self.base_url}/followers/users",
                params={"per_page": 80, "page": page}
            )
            
            if response.status_code != 200:
                break
            
            data = response.json()
            if not data:
                break
            
            all_followers.extend(data)
            page += 1
            
            # Rate limiting
            await asyncio.sleep(self.rate_limit_delay)
        
        return all_followers
    
    async def fetch_comments(self, article_id: int) -> List[Dict[str, Any]]:
        """
        Fetch comments for a specific article
        
        Args:
            article_id: DEV.to article ID
        Returns: List of comment dictionaries
        """
        if not self.http_client:
            raise RuntimeError("Service not initialized")
        
        response = await self.http_client.get(
            f"{self.base_url}/comments",
            params={"a_id": article_id}
        )
        
        if response.status_code == 200:
            return response.json()
        return []
    
    async def fetch_historical_analytics(
        self,
        article_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical daily analytics (undocumented endpoint)
        
        Replaces: _fetch_historical_analytics() from devto_tracker.py
        
        NOTE: DEV.to API changed - now requires 'start' and 'end' parameters
        Defaults to last 90 days if not specified
        
        Returns: Dict mapping date strings to analytics data
        """
        if not self.http_client:
            raise RuntimeError("Service not initialized")
        
        # Calculate default date range (last 90 days)
        from datetime import timedelta
        
        if not end_date:
            end_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        if not start_date:
            start_datetime = datetime.now(timezone.utc) - timedelta(days=90)
            start_date = start_datetime.strftime('%Y-%m-%d')
        
        response = await self.http_client.get(
            f"{self.base_url}/analytics/historical",
            params={
                "article_id": article_id,
                "start": start_date,
                "end": end_date
            }
        )
        
        if response.status_code == 200:
            return response.json()
        
        return {}
    
    async def fetch_referrers(self, article_id: int) -> Dict[str, Any]:
        """
        Fetch traffic referrers (undocumented endpoint)
        
        Replaces: _fetch_referrers() from devto_tracker.py
        Returns: Dict with 'domains' key containing list of referrer data
        """
        if not self.http_client:
            raise RuntimeError("Service not initialized")
        
        response = await self.http_client.get(
            f"{self.base_url}/analytics/referrers",
            params={"article_id": article_id}
        )
        
        if response.status_code == 200:
            return response.json()
        return {}
    
    # ========================================================================
    # DATABASE SYNC METHODS (SQLAlchemy Core + AsyncConnection)
    # ========================================================================
    
    @staticmethod
    def _convert_tags(tag_list: List[str]) -> tuple[str, List[str]]:
        """
        Convert tag list to both formats for PostgreSQL
        
        Returns:
            tuple: (JSON string for 'tags' JSONB, list for 'tag_list' ARRAY)
        
        Pattern preserves SQLite behavior:
        - tags: JSON string like '["python", "sql"]'
        - tag_list: Python list for ARRAY(String) type
        """
        return json.dumps(tag_list), tag_list
    
    @staticmethod
    def _ensure_utc(dt_string: Optional[str]) -> Optional[datetime]:
        """
        Convert ISO datetime string to timezone-aware UTC datetime
        
        Args:
            dt_string: ISO 8601 datetime string
        Returns:
            Timezone-aware datetime in UTC, or None
        """
        if not dt_string:
            return None
        
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    
    async def sync_articles(
        self,
        collected_at: Optional[datetime] = None
    ) -> int:
        """
        Sync article metrics to database
        
        Replaces: collect_snapshot() from devto_tracker.py
        Uses: INSERT ... ON CONFLICT DO NOTHING for idempotency
        
        Returns: Number of articles synced
        """
        if collected_at is None:
            collected_at = datetime.now(timezone.utc)
        
        articles = await self.fetch_articles()
        print(f"📡 Syncing {len(articles)} articles...")
        
        async with self.engine.begin() as conn:
            for article in articles:
                # Convert tags to both formats
                tags_json, tag_list_array = self._convert_tags(article.get('tag_list', []))
                
                # Build insert statement with on_conflict_do_nothing
                stmt = pg_insert(article_metrics).values(
                    collected_at=collected_at,
                    article_id=article['id'],
                    title=article.get('title'),
                    slug=article.get('slug'),
                    published_at=self._ensure_utc(article.get('published_at')),
                    views=article.get('page_views_count', 0),
                    reactions=article.get('public_reactions_count', 0),
                    comments=article.get('comments_count', 0),
                    reading_time_minutes=article.get('reading_time_minutes'),
                    tags=tags_json,
                    tag_list=tag_list_array,
                    is_deleted=False,
                )
                
                # ON CONFLICT DO NOTHING (idempotent)
                stmt = stmt.on_conflict_do_nothing(
                    constraint='uq_article_metrics_collected_article'
                )
                
                await conn.execute(stmt)
        
        print(f"✅ {len(articles)} articles synced")
        return len(articles)
    
    async def sync_followers(
        self,
        collected_at: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Sync follower count with delta calculation
        
        Replaces: _collect_followers() from devto_tracker.py
        Returns: Dict with 'count' and 'delta' keys
        """
        if collected_at is None:
            collected_at = datetime.now(timezone.utc)
        
        print("👥 Syncing followers...")
        followers = await self.fetch_followers()
        count = len(followers)
        
        async with self.engine.begin() as conn:
            # Get last follower count for delta calculation
            query = select(follower_events.c.follower_count).order_by(
                follower_events.c.collected_at.desc()
            ).limit(1)
            
            result = await conn.execute(query)
            row = result.first()
            last_count = row[0] if row else 0
            delta = count - last_count
            
            # Insert new follower event
            stmt = insert(follower_events).values(
                collected_at=collected_at,
                follower_count=count,
                new_followers_since_last=delta,
            )
            await conn.execute(stmt)
        
        print(f"👥 Followers: {count} (Δ{delta:+d})")
        return {'count': count, 'delta': delta}
    
    async def sync_comments(
        self,
        articles: Optional[List[Dict[str, Any]]] = None,
        collected_at: Optional[datetime] = None
    ) -> int:
        """
        Sync comments for all published articles
        
        Replaces: _collect_comments() from devto_tracker.py
        Uses: INSERT ... ON CONFLICT DO NOTHING for idempotency
        
        Returns: Number of new comments
        """
        if collected_at is None:
            collected_at = datetime.now(timezone.utc)
        
        if articles is None:
            articles = await self.fetch_articles()
        
        print("💬 Syncing comments...")
        new_comments = 0
        
        async with self.engine.begin() as conn:
            for article in articles:
                # Skip unpublished articles
                if not article.get('published_at'):
                    continue
                
                article_comments = await self.fetch_comments(article['id'])
                
                for comment in article_comments:
                    user = comment.get('user', {})
                    body_html = comment.get('body_html', '')
                    
                    # Build insert with on_conflict_do_nothing
                    stmt = pg_insert(comments).values(
                        comment_id=comment['id_code'],
                        article_id=article['id'],
                        article_title=article.get('title'),
                        author_username=user.get('username'),
                        author_name=user.get('name'),
                        body_html=body_html,
                        body_length=len(body_html),
                        created_at=self._ensure_utc(comment.get('created_at')),
                        collected_at=collected_at,
                    )
                    
                    # ON CONFLICT DO NOTHING (unique constraint on comment_id)
                    stmt = stmt.on_conflict_do_nothing(
                        constraint='uq_comments_comment_id'
                    )
                    
                    result = await conn.execute(stmt)
                    if result.rowcount > 0:
                        new_comments += 1
                
                # Rate limiting between articles
                await asyncio.sleep(self.rate_limit_delay)
        
        print(f"💬 New comments: {new_comments}")
        return new_comments
    
    async def sync_rich_analytics(
        self,
        articles: Optional[List[Dict[str, Any]]] = None,
        collected_at: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        Sync rich analytics: historical daily data and referrers
        
        Replaces: collect_rich_analytics() from devto_tracker.py
        Uses: INSERT ... ON CONFLICT DO UPDATE for daily_analytics
        
        Returns: Dict with counts of synced records
        """
        if collected_at is None:
            collected_at = datetime.now(timezone.utc)
        
        if articles is None:
            articles = await self.fetch_articles()
        
        print("📊 Syncing rich analytics...")
        daily_count = 0
        referrer_count = 0
        
        for article in articles:
            # Skip unpublished articles
            if not article.get('published_at'):
                continue
            
            # Sync historical daily analytics
            historical = await self.fetch_historical_analytics(article['id'])
            if historical:
                daily_count += await self._sync_daily_analytics(
                    article['id'],
                    historical,
                    collected_at
                )
            
            # Sync referrers
            referrer_data = await self.fetch_referrers(article['id'])
            if referrer_data:
                referrer_count += await self._sync_referrers(
                    article['id'],
                    referrer_data,
                    collected_at
                )
            
            # Rate limiting
            await asyncio.sleep(self.rate_limit_delay)
        
        print(f"📊 Synced: {daily_count} daily records, {referrer_count} referrers")
        return {'daily_analytics': daily_count, 'referrers': referrer_count}
    
    async def _sync_daily_analytics(
        self,
        article_id: int,
        historical_data: Dict[str, Dict[str, Any]],
        collected_at: datetime
    ) -> int:
        """
        Sync daily analytics with upsert pattern
        
        Uses: INSERT ... ON CONFLICT DO UPDATE
        Constraint: uq_daily_analytics_article_date
        """
        from datetime import date as date_type
        
        count = 0
        
        async with self.engine.begin() as conn:
            for date_str, stats in historical_data.items():
                # Convert date string to date object (YYYY-MM-DD -> date)
                date_obj = date_type.fromisoformat(date_str)
                
                # Build insert statement
                stmt = pg_insert(daily_analytics).values(
                    article_id=article_id,
                    date=date_obj,
                    page_views=stats['page_views']['total'],
                    average_read_time_seconds=stats['page_views'].get('average_read_time_in_seconds', 0),
                    total_read_time_seconds=stats['page_views'].get('total_read_time_in_seconds', 0),
                    reactions_total=stats['reactions']['total'],
                    reactions_like=stats['reactions'].get('like', 0),
                    reactions_readinglist=stats['reactions'].get('readinglist', 0),
                    reactions_unicorn=stats['reactions'].get('unicorn', 0),
                    comments_total=stats['comments']['total'],
                    follows_total=stats['follows']['total'],
                    collected_at=collected_at,
                )
                
                # ON CONFLICT DO UPDATE (update with latest values)
                stmt = stmt.on_conflict_do_update(
                    constraint='uq_daily_analytics_article_date',
                    set_={
                        'page_views': stmt.excluded.page_views,
                        'average_read_time_seconds': stmt.excluded.average_read_time_seconds,
                        'total_read_time_seconds': stmt.excluded.total_read_time_seconds,
                        'reactions_total': stmt.excluded.reactions_total,
                        'reactions_like': stmt.excluded.reactions_like,
                        'reactions_readinglist': stmt.excluded.reactions_readinglist,
                        'reactions_unicorn': stmt.excluded.reactions_unicorn,
                        'comments_total': stmt.excluded.comments_total,
                        'follows_total': stmt.excluded.follows_total,
                        'collected_at': stmt.excluded.collected_at,
                    }
                )
                
                await conn.execute(stmt)
                count += 1
        
        return count
    
    async def _sync_referrers(
        self,
        article_id: int,
        referrer_data: Dict[str, Any],
        collected_at: datetime
    ) -> int:
        """
        Sync traffic referrers as time-series data
        
        Uses: INSERT ... ON CONFLICT DO NOTHING
        Note: Constraint is on (article_id, domain, collected_at) for time-series tracking
        Each collection creates a new snapshot of referrer counts
        """
        count = 0
        domains = referrer_data.get('domains', [])
        
        async with self.engine.begin() as conn:
            for ref in domains:
                # Skip entries with missing domain
                if not ref.get('domain'):
                    continue
                
                # Build insert statement
                stmt = pg_insert(referrers).values(
                    article_id=article_id,
                    domain=ref['domain'],
                    count=ref['count'],
                    collected_at=collected_at,
                )
                
                # ON CONFLICT DO NOTHING (time-series: don't update existing snapshots)
                stmt = stmt.on_conflict_do_nothing(
                    constraint='uq_referrers_article_domain_time'
                )
                
                await conn.execute(stmt)
                count += 1
        
        return count
    
    # ========================================================================
    # HIGH-LEVEL ORCHESTRATION METHODS
    # ========================================================================
    
    async def sync_all(self) -> Dict[str, Any]:
        """
        Sync everything: articles, followers, comments, and rich analytics
        
        Replaces: collect_all() from devto_tracker.py
        
        Returns: Summary dict with all sync counts
        """
        collected_at = datetime.now(timezone.utc)
        print(f"\n{'='*80}")
        print(f"🚀 FULL SYNC STARTED: {collected_at.isoformat()}")
        print(f"{'='*80}\n")
        
        # Fetch articles once for reuse
        articles = await self.fetch_articles()
        
        # Sync in logical order
        article_count = await self.sync_articles(collected_at)
        follower_data = await self.sync_followers(collected_at)
        comment_count = await self.sync_comments(articles, collected_at)
        analytics_data = await self.sync_rich_analytics(articles, collected_at)
        
        summary = {
            'collected_at': collected_at.isoformat(),
            'articles': article_count,
            'followers': follower_data,
            'comments': comment_count,
            'daily_analytics': analytics_data['daily_analytics'],
            'referrers': analytics_data['referrers'],
        }
        
        print(f"\n{'='*80}")
        print(f"✅ FULL SYNC COMPLETE")
        print(f"{'='*80}")
        print(f"📊 Summary:")
        print(f"   Articles: {summary['articles']}")
        print(f"   Followers: {summary['followers']['count']} (Δ{summary['followers']['delta']:+d})")
        print(f"   New Comments: {summary['comments']}")
        print(f"   Daily Analytics: {summary['daily_analytics']} records")
        print(f"   Referrers: {summary['referrers']} domains")
        print(f"{'='*80}\n")
        
        return summary


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def create_service(api_key: Optional[str] = None) -> DevToService:
    """
    Create and initialize DevToService
    
    Args:
        api_key: DEV.to API key (uses DEVTO_API_KEY env var if not provided)
    
    Returns:
        Initialized DevToService ready for use with async context manager
    """
    # Load environment variables from .env file
    load_dotenv()
    
    if api_key is None:
        api_key = os.getenv('DEVTO_API_KEY')
        if not api_key:
            raise ValueError("API key required. Set DEVTO_API_KEY environment variable.")
    
    return DevToService(api_key)


async def main():
    """CLI entry point for testing"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m app.services.devto_service [--articles|--followers|--comments|--rich|--all]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    try:
        async with await create_service() as service:
            if action == '--articles':
                await service.sync_articles()
            elif action == '--followers':
                await service.sync_followers()
            elif action == '--comments':
                await service.sync_comments()
            elif action == '--rich':
                await service.sync_rich_analytics()
            elif action == '--all':
                await service.sync_all()
            else:
                print(f"Unknown action: {action}")
                sys.exit(1)
    
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
