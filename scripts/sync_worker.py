#!/usr/bin/env python3
"""
Standalone Asynchronous Sync Worker for DEV.to Analytics

Designed to run via cron for scheduled data synchronization.
Uses PostgreSQL advisory locks to prevent concurrent execution.

Usage:
    python3 scripts/sync_worker.py

Exit Codes:
    0 - Success or lock unavailable (safe for cron)
    1 - Error occurred (check logs)

Environment:
    Loads from .env file in project root
"""

import asyncio
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from app.services.devto_service import DevToService
from app.services.analytics_service import AnalyticsService
from app.services.theme_service import ThemeService
from app.services.nlp_service import NLPService


def log(message: str, emoji: str = "ℹ️"):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {emoji} {message}", flush=True)


def log_error(message: str):
    """Print error to stderr"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] ❌ ERROR: {message}", file=sys.stderr, flush=True)


def get_database_url() -> str:
    """Build PostgreSQL connection URL from environment variables"""
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'devto_analytics')
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD')
    
    if not user or not password:
        raise ValueError("Missing required environment variables: POSTGRES_USER, POSTGRES_PASSWORD")
    
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


async def acquire_advisory_lock(engine: AsyncEngine, lock_id: int = 12345) -> bool:
    """
    Try to acquire PostgreSQL advisory lock.
    
    Returns True if lock acquired, False if already held by another process.
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": lock_id}
        )
        acquired = result.scalar()
        await conn.commit()
        return acquired


async def release_advisory_lock(engine: AsyncEngine, lock_id: int = 12345):
    """Release PostgreSQL advisory lock"""
    async with engine.connect() as conn:
        await conn.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": lock_id}
        )
        await conn.commit()


async def run_sync_pipeline():
    """
    Main sync pipeline execution.
    
    Phases:
        1. Collection - Fetch latest article metrics from DEV.to API
        2. Enrichment - Sync rich analytics (historical data)
        3. Intelligence - Classify articles by theme (DNA analysis)
        4. Refresh Cache - Update article_stats_cache for fast queries
    """
    engine: Optional[AsyncEngine] = None
    lock_acquired = False
    lock_id = 98765  # Unique ID for sync worker lock
    
    try:
        # Load environment variables
        load_dotenv()
        log("Starting Sync Pipeline...", "🚀")
        
        # Create async engine with connection pooling
        db_url = get_database_url()
        engine = create_async_engine(
            db_url,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            echo=False
        )
        log("Database connection established", "🔌")
        
        # Try to acquire advisory lock
        lock_acquired = await acquire_advisory_lock(engine, lock_id)
        if not lock_acquired:
            log("Another sync process is running. Exiting gracefully.", "⏳")
            return 0  # Not an error - just skip this run
        
        # Load DEV.to credentials from environment
        devto_api_key = os.getenv('DEVTO_API_KEY')
        if not devto_api_key:
            raise ValueError("Missing required environment variable: DEVTO_API_KEY")
        
        # ═══════════════════════════════════════════════════════════════════
        # Phase 1: Collection - Sync latest article metrics
        # ═══════════════════════════════════════════════════════════════════
        log("Phase 1/4: Collection - Fetching latest article metrics", "📥")
        phase1_start = datetime.now()
        
        async with DevToService(api_key=devto_api_key, db_url=db_url) as devto_service:
            articles_synced = await devto_service.sync_articles()
        
        phase1_duration = (datetime.now() - phase1_start).total_seconds()
        log(
            f"Collection: {articles_synced} articles updated "
            f"in {phase1_duration:.1f}s",
            "✅"
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # Phase 2: Enrichment - Sync rich analytics (historical data)
        # ═══════════════════════════════════════════════════════════════════
        log("Phase 2/4: Enrichment - Syncing historical analytics", "📊")
        phase2_start = datetime.now()
        
        async with DevToService(api_key=devto_api_key, db_url=db_url) as devto_service:
            enrichment_result = await devto_service.sync_rich_analytics()
        
        phase2_duration = (datetime.now() - phase2_start).total_seconds()
        daily_count = enrichment_result.get('daily_analytics', 0)
        referrer_count = enrichment_result.get('referrers', 0)
        total_snapshots = daily_count + referrer_count
        log(
            f"Enrichment: {total_snapshots} records synced ({daily_count} daily + {referrer_count} referrers) "
            f"in {phase2_duration:.1f}s",
            "✅"
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # Phase 3: Intelligence - Theme classification (DNA analysis)
        # ═══════════════════════════════════════════════════════════════════
        log("Phase 3/4: Intelligence - Classifying articles by theme", "🧬")
        phase3_start = datetime.now()
        
        # Initialize remaining services (not context managers)
        analytics_service = AnalyticsService(engine=engine)
        theme_service = ThemeService(engine=engine)
        nlp_service = NLPService(engine=engine)
        
        # Ensure default themes exist
        themes_created = await theme_service.seed_default_themes()
        if themes_created > 0:
            log(f"Seeded {themes_created} default themes", "🌱")
        
        # Classify all articles
        classification_result = await theme_service.classify_all_articles()
        
        phase3_duration = (datetime.now() - phase3_start).total_seconds()
        classified_count = classification_result.get('classified', 0)
        log(
            f"Intelligence: {classified_count} articles classified "
            f"in {phase3_duration:.1f}s",
            "✅"
        )
        
        # ═══════════════════════════════════════════════════════════════════
        # Phase 4: Refresh Cache - Update materialized aggregations
        # ═══════════════════════════════════════════════════════════════════
        log("Phase 4/4: Refreshing analytics cache", "🔄")
        phase4_start = datetime.now()
        
        # Update article_stats_cache table
        # Note: This assumes you have a cache refresh method in analytics_service
        # If not, you can create one or use REFRESH MATERIALIZED VIEW directly
        async with engine.begin() as conn:
            # Check if article_stats_cache table exists
            cache_exists = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'article_stats_cache'
                    )
                """)
            )
            
            if cache_exists.scalar():
                # If it's a materialized view, refresh it
                await conn.execute(text("REFRESH MATERIALIZED VIEW article_stats_cache"))
                log("Materialized view refreshed", "✅")
            else:
                # Otherwise just log that cache doesn't exist yet
                log("Cache table not found (skipping)", "⏭️")
        
        phase4_duration = (datetime.now() - phase4_start).total_seconds()
        log(f"Cache refresh completed in {phase4_duration:.1f}s", "✅")
        
        # ═══════════════════════════════════════════════════════════════════
        # Summary
        # ═══════════════════════════════════════════════════════════════════
        total_duration = (
            phase1_duration + phase2_duration + 
            phase3_duration + phase4_duration
        )
        
        log(
            f"Pipeline completed successfully in {total_duration:.1f}s",
            "🎉"
        )
        
        # Print summary stats
        print()
        print("=" * 70)
        print("📊 SYNC SUMMARY")
        print("=" * 70)
        print(f"  Articles Updated:     {articles_synced}")
        print(f"  Daily Analytics:      {daily_count}")
        print(f"  Referrers Synced:     {referrer_count}")
        print(f"  Articles Classified:  {classified_count}")
        print(f"  Total Duration:       {total_duration:.1f}s")
        print("=" * 70)
        print()
        
        return 0  # Success
        
    except KeyboardInterrupt:
        log("Sync interrupted by user", "⚠️")
        return 1
        
    except Exception as e:
        log_error(f"Pipeline failed: {str(e)}")
        print("\n" + "=" * 70, file=sys.stderr)
        print("STACK TRACE:", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        print("=" * 70 + "\n", file=sys.stderr)
        return 1
        
    finally:
        # Release lock if acquired
        if lock_acquired and engine:
            try:
                await release_advisory_lock(engine, lock_id)
                log("Advisory lock released", "🔓")
            except Exception as e:
                log_error(f"Failed to release lock: {e}")
        
        # Dispose engine
        if engine:
            await engine.dispose()
            log("Database connection closed", "🔌")


async def main():
    """Entry point"""
    exit_code = await run_sync_pipeline()
    sys.exit(exit_code)


if __name__ == "__main__":
    # Run the async pipeline
    asyncio.run(main())
