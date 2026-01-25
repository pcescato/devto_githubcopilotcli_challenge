"""
Theme Classification Service - PostgreSQL Edition

Provides async thematic classification and Author DNA analysis.
Ported from core/topic_intelligence.py (SQLite, sync) to PostgreSQL async.
"""

import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.tables import author_themes, article_theme_mapping, article_metrics


class ThemeService:
    """
    Async service for thematic classification and Author DNA analysis
    
    Business Logic (preserved from original):
    - Theme matching: case-insensitive keyword search in (title + tags)
    - Selection: HIGHEST ABSOLUTE match_count (not confidence ratio!)
    - Tie-breaker: If same match_count, use highest confidence_score
    - Fallback: All match_counts = 0 → 'Free Exploration'
    """
    
    # Default themes (from original topic_intelligence.py:11-15)
    DEFAULT_THEMES = {
        "Expertise Tech": ["sql", "database", "python", "cloud", "docker", "vps", "astro", "hugo", "vector", "cte"],
        "Human & Career": ["cv", "career", "feedback", "developer", "learning", "growth"],
        "Culture & Agile": ["agile", "scrum", "performance", "theater", "laziness", "management"]
    }
    
    def __init__(
        self,
        engine: Optional[AsyncEngine] = None,
        db_url: Optional[str] = None
    ):
        """
        Initialize theme service
        
        Args:
            engine: AsyncEngine instance (creates from db_url if not provided)
            db_url: PostgreSQL connection URL (uses env vars if not provided)
        """
        if engine is None:
            if db_url is None:
                db_url = self._get_async_database_url()
            engine = create_async_engine(
                db_url,
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )
        self.engine = engine
    
    def _get_async_database_url(self) -> str:
        """Construct async PostgreSQL URL from environment variables"""
        # Load .env if not already loaded
        load_dotenv()
        
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        database = os.getenv('POSTGRES_DB', 'devto_analytics')
        user = os.getenv('POSTGRES_USER')
        password = os.getenv('POSTGRES_PASSWORD')
        
        if not user or not password:
            raise ValueError(
                "Missing PostgreSQL credentials. Set POSTGRES_USER and POSTGRES_PASSWORD"
            )
        
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    async def seed_default_themes(self) -> int:
        """
        Insert default themes into author_themes table
        
        Uses INSERT ... ON CONFLICT DO NOTHING for idempotency
        
        Returns:
            Number of themes created (not skipped)
        """
        created = 0
        
        async with self.engine.begin() as conn:
            for theme_name, keywords in self.DEFAULT_THEMES.items():
                stmt = pg_insert(author_themes).values(
                    theme_name=theme_name,
                    keywords=keywords,
                    created_at=datetime.now(timezone.utc)
                )
                
                # ON CONFLICT DO NOTHING (idempotent)
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=['theme_name']
                )
                
                result = await conn.execute(stmt)
                if result.rowcount > 0:
                    created += 1
        
        print(f"✅ Seeded {created} themes (skipped {len(self.DEFAULT_THEMES) - created} existing)")
        return created
    
    async def classify_article(self, article_id: int) -> Dict[str, Any]:
        """
        Classify a single article into thematic categories
        
        CRITICAL: Gets LATEST metadata from article_metrics to avoid duplicates
        
        Algorithm (preserved from original):
        1. Get latest title + tag_list from article_metrics
        2. For each theme, count absolute keyword matches (case-insensitive)
        3. Select theme with HIGHEST match_count
        4. Tie-breaker: Use highest confidence_score if match_counts equal
        5. Fallback: If all match_counts = 0, assign 'Free Exploration'
        
        Args:
            article_id: Article ID to classify
            
        Returns:
            Dict with classification results
        """
        async with self.engine.begin() as conn:
            # Get latest article metadata (CRITICAL: ORDER BY collected_at DESC LIMIT 1)
            result = await conn.execute(
                select(
                    article_metrics.c.title,
                    article_metrics.c.tag_list
                )
                .where(article_metrics.c.article_id == article_id)
                .order_by(article_metrics.c.collected_at.desc())
                .limit(1)
            )
            
            article = result.fetchone()
            if not article:
                raise ValueError(f"Article {article_id} not found in article_metrics")
            
            article_dict = dict(article._mapping)
            title = article_dict['title'] or ''
            tag_list = article_dict['tag_list'] or []
            
            # Combine searchable text
            searchable_text = (title + ' ' + ' '.join(tag_list)).lower()
            
            # Get all themes
            result = await conn.execute(
                select(
                    author_themes.c.id,
                    author_themes.c.theme_name,
                    author_themes.c.keywords
                )
            )
            
            themes = [dict(row._mapping) for row in result]
            
            # Calculate match scores for each theme
            theme_scores = {}
            for theme in themes:
                keywords = theme['keywords']
                matched_kws = []
                match_count = 0
                
                for kw in keywords:
                    if kw.lower() in searchable_text:
                        match_count += 1
                        matched_kws.append(kw)
                
                confidence_score = match_count / len(keywords) if keywords else 0
                
                theme_scores[theme['id']] = {
                    'theme_name': theme['theme_name'],
                    'match_count': match_count,
                    'confidence_score': confidence_score,
                    'matched_keywords': matched_kws
                }
            
            # Select best theme (CRITICAL: preserve original algorithm)
            if all(score['match_count'] == 0 for score in theme_scores.values()):
                # Fallback: No matches found
                # Check if 'Free Exploration' theme exists
                result = await conn.execute(
                    select(author_themes.c.id)
                    .where(author_themes.c.theme_name == 'Free Exploration')
                )
                free_theme = result.fetchone()
                
                if not free_theme:
                    # Create 'Free Exploration' theme
                    stmt = pg_insert(author_themes).values(
                        theme_name='Free Exploration',
                        keywords=[],
                        created_at=datetime.now(timezone.utc)
                    ).on_conflict_do_nothing(index_elements=['theme_name'])
                    await conn.execute(stmt)
                    
                    # Get the ID
                    result = await conn.execute(
                        select(author_themes.c.id)
                        .where(author_themes.c.theme_name == 'Free Exploration')
                    )
                    free_theme = result.fetchone()
                
                best_theme_id = free_theme[0]
                best_score = {
                    'theme_name': 'Free Exploration',
                    'match_count': 0,
                    'confidence_score': 0.0,
                    'matched_keywords': []
                }
            else:
                # Sort by: 1) match_count DESC, 2) confidence_score DESC (tie-breaker)
                best_theme_id = max(
                    theme_scores.items(),
                    key=lambda x: (x[1]['match_count'], x[1]['confidence_score'])
                )[0]
                best_score = theme_scores[best_theme_id]
            
            # Insert/update classification
            stmt = pg_insert(article_theme_mapping).values(
                article_id=article_id,
                theme_id=best_theme_id,
                confidence_score=best_score['confidence_score'],
                matched_keywords=best_score['matched_keywords'],
                classified_at=datetime.now(timezone.utc)
            )
            
            # ON CONFLICT DO UPDATE (allow re-classification)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_article_theme_article_theme',
                set_={
                    'confidence_score': stmt.excluded.confidence_score,
                    'matched_keywords': stmt.excluded.matched_keywords,
                    'classified_at': stmt.excluded.classified_at
                }
            )
            
            await conn.execute(stmt)
        
        return {
            'article_id': article_id,
            'theme_name': best_score['theme_name'],
            'match_count': best_score['match_count'],
            'confidence_score': best_score['confidence_score'],
            'matched_keywords': best_score['matched_keywords']
        }
    
    async def classify_all_articles(self) -> Dict[str, int]:
        """
        Classify all published articles
        
        Returns:
            Dict with counts: {'total': N, 'classified': M, 'errors': K}
        """
        async with self.engine.connect() as conn:
            # Get DISTINCT published articles (avoid duplicates from snapshots)
            result = await conn.execute(
                select(
                    article_metrics.c.article_id,
                    func.max(article_metrics.c.title).label('title')
                )
                .where(article_metrics.c.published_at.isnot(None))
                .group_by(article_metrics.c.article_id)
            )
            
            articles = [dict(row._mapping) for row in result]
        
        total = len(articles)
        classified = 0
        errors = 0
        
        print(f"📊 Classifying {total} published articles...")
        
        for i, article in enumerate(articles, 1):
            article_id = article['article_id']
            
            try:
                result = await self.classify_article(article_id)
                classified += 1
                
                # Log progress every 10 articles
                if i % 10 == 0:
                    print(f"  Progress: {i}/{total} ({i/total*100:.0f}%)")
                
            except Exception as e:
                print(f"  ⚠️  Error classifying article {article_id}: {e}")
                errors += 1
        
        print(f"✅ Classification complete: {classified} classified, {errors} errors")
        
        return {
            'total': total,
            'classified': classified,
            'errors': errors
        }
    
    async def generate_dna_report(self) -> Dict[str, Any]:
        """
        Generate Author DNA report
        
        Analyzes content distribution across themes with engagement metrics
        
        Returns:
            Dict with theme statistics
        """
        async with self.engine.connect() as conn:
            # Query: article_theme_mapping JOIN article_metrics
            # Aggregate by theme
            result = await conn.execute(text("""
                SELECT 
                    t.theme_name,
                    COUNT(DISTINCT atm.article_id) as article_count,
                    COALESCE(SUM(subq.max_views), 0) as total_views,
                    COALESCE(SUM(subq.max_reactions), 0) as total_reactions,
                    COALESCE(AVG(subq.max_views), 0) as avg_views,
                    CASE 
                        WHEN SUM(subq.max_views) > 0 
                        THEN (SUM(subq.max_reactions)::float / SUM(subq.max_views) * 100)
                        ELSE 0 
                    END as engagement_pct
                FROM devto_analytics.article_theme_mapping atm
                JOIN devto_analytics.author_themes t ON atm.theme_id = t.id
                JOIN (
                    SELECT 
                        article_id, 
                        MAX(views) as max_views, 
                        MAX(reactions) as max_reactions
                    FROM devto_analytics.article_metrics
                    GROUP BY article_id
                ) subq ON atm.article_id = subq.article_id
                GROUP BY t.theme_name
                ORDER BY avg_views DESC
            """))
            
            theme_stats = [dict(row._mapping) for row in result]
        
        return {'themes': theme_stats}
    
    def print_dna_report(self, report_data: Dict[str, Any]):
        """
        Print Author DNA report (preserves original format)
        
        Args:
            report_data: Output from generate_dna_report()
        """
        themes = report_data.get('themes', [])
        
        if not themes:
            print("\n⚠️  No classified articles found. Run --classify-all first.")
            return
        
        print("\n" + "🧬" + " --- AUTHOR CONTENT DNA (MIRROR REPORT) ---")
        print("=" * 80)
        print(f"{'Thematic Axis':<25} {'Articles':<10} {'Avg Views':<12} {'Engagement %':<12}")
        print("-" * 80)
        
        for theme in themes:
            if theme['article_count'] > 0:
                print(f"{theme['theme_name']:<25} "
                      f"{theme['article_count']:<10} "
                      f"{theme['avg_views']:<12.0f} "
                      f"{theme['engagement_pct']:<12.2f}%")
        
        # Pragmatic interpretation
        if themes:
            print("\n💡 PRAGMATIC INTERPRETATION:")
            
            # Best engagement
            best_engage = max(themes, key=lambda x: x['engagement_pct'])
            print(f"👉 Your community engages most intensely with the '{best_engage['theme_name']}' axis.")
            
            # Best views
            best_views = max(themes, key=lambda x: x['avg_views'])
            print(f"👉 The '{best_views['theme_name']}' axis is your strongest driver for raw visibility.")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def create_theme_service(engine: Optional[AsyncEngine] = None) -> ThemeService:
    """
    Create and initialize ThemeService
    
    Args:
        engine: Optional AsyncEngine (creates from env vars if not provided)
    
    Returns:
        Initialized ThemeService
    """
    load_dotenv()
    return ThemeService(engine=engine)


async def main():
    """CLI entry point"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Theme Classification and Author DNA Analysis',
        epilog='Port of core/topic_intelligence.py to PostgreSQL'
    )
    
    parser.add_argument('--seed', action='store_true',
                       help='Seed default themes into database')
    parser.add_argument('--classify-all', action='store_true',
                       help='Classify all published articles')
    parser.add_argument('--classify-article', type=int, metavar='ID',
                       help='Classify specific article by ID')
    parser.add_argument('--report', action='store_true',
                       help='Generate and print DNA report')
    parser.add_argument('--full', action='store_true',
                       help='Complete workflow: seed + classify + report')
    
    args = parser.parse_args()
    
    # Check if any action specified
    if not any([args.seed, args.classify_all, args.classify_article, args.report, args.full]):
        parser.print_help()
        sys.exit(1)
    
    try:
        service = await create_theme_service()
        
        if args.full:
            # Complete workflow
            print("🚀 Running complete workflow...\n")
            await service.seed_default_themes()
            print()
            await service.classify_all_articles()
            print()
            report = await service.generate_dna_report()
            service.print_dna_report(report)
            
        else:
            if args.seed:
                await service.seed_default_themes()
            
            if args.classify_article:
                result = await service.classify_article(args.classify_article)
                print(f"\n✅ Article {result['article_id']} classified:")
                print(f"  Theme: {result['theme_name']}")
                print(f"  Match count: {result['match_count']}")
                print(f"  Confidence: {result['confidence_score']:.2%}")
                print(f"  Keywords: {', '.join(result['matched_keywords'])}")
            
            if args.classify_all:
                await service.classify_all_articles()
            
            if args.report:
                report = await service.generate_dna_report()
                service.print_dna_report(report)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
