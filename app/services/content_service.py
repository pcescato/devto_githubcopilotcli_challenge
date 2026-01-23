#!/usr/bin/env python3
r"""
Content Service - Async content collection and parsing for DEV.to articles

Migrated from: content_collector.py
Uses: httpx.AsyncClient, AsyncConnection, PostgreSQL

Responsibilities:
- Fetch full article content (body_markdown) from DEV.to API
- Parse markdown to extract code blocks, links, images, headings
- Calculate content metrics (word count, char count, etc.)
- Store content in article_content, article_code_blocks, article_links tables
- ON CONFLICT DO UPDATE for idempotency

Business Logic:
- Code blocks: ```language\ncode\n``` pattern
- Links: [text](url) pattern
- Images: ![alt](url) pattern
- Headings: ^#{1,6}\s+.+$ pattern
- Link types: anchor (#), internal (dev.to), external (http), relative
- Word count: Excludes code blocks
"""

import asyncio
import re
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import os

import httpx
from sqlalchemy import select, delete, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.dialects.postgresql import insert

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContentService:
    """
    Async content collection and parsing service
    
    Fetches article content from DEV.to API and parses markdown to extract:
    - Code blocks with language tags
    - Links with type classification
    - Content metrics (word count, images, headings)
    """
    
    def __init__(
        self,
        api_key: str,
        engine: Optional[AsyncEngine] = None,
        db_url: Optional[str] = None
    ):
        """
        Initialize ContentService
        
        Args:
            api_key: DEV.to API key
            engine: Optional SQLAlchemy async engine
            db_url: Optional database URL (if engine not provided)
        """
        self.api_key = api_key
        self.base_url = "https://dev.to/api"
        
        if engine:
            self.engine = engine
        elif db_url:
            self.engine = create_async_engine(
                db_url,
                echo=False,
                pool_size=20,
                max_overflow=10
            )
        else:
            raise ValueError("Either engine or db_url must be provided")
    
    async def get_articles_to_collect(
        self,
        mode: str = "new",
        specific_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of articles that need content collection
        
        Migrated from: content_collector.py:105-167
        
        Args:
            mode: "all" (all articles), "new" (not yet collected)
            specific_id: Optional specific article ID to collect
        
        Returns:
            List of dicts with article_id and title
        """
        from app.db.tables import article_metrics as am, article_content as ac
        
        async with self.engine.connect() as conn:
            if specific_id:
                # Get specific article
                query = (
                    select(am.c.article_id, am.c.title)
                    .where(am.c.article_id == specific_id)
                    .distinct()
                )
            elif mode == "all":
                # Get all articles
                query = (
                    select(am.c.article_id, am.c.title)
                    .where(am.c.published_at.isnot(None))
                    .distinct()
                    .order_by(am.c.article_id)
                )
            elif mode == "new":
                # Get articles not yet in article_content (LEFT JOIN ... IS NULL)
                query = (
                    select(am.c.article_id, am.c.title)
                    .select_from(
                        am.outerjoin(ac, am.c.article_id == ac.c.article_id)
                    )
                    .where(
                        and_(
                            am.c.published_at.isnot(None),
                            ac.c.article_id.is_(None)
                        )
                    )
                    .distinct()
                    .order_by(am.c.article_id)
                )
            else:
                raise ValueError(f"Unknown mode: {mode}")
            
            result = await conn.execute(query)
            articles = [dict(row._mapping) for row in result]
            
            logger.info(f"Found {len(articles)} articles to collect (mode={mode})")
            return articles
    
    async def fetch_article_content(self, article_id: int) -> Optional[Dict]:
        """
        Fetch article content from DEV.to API
        
        Migrated from: content_collector.py:169-191
        
        Args:
            article_id: DEV.to article ID
        
        Returns:
            Dict with body_markdown, body_html, etc. or None if error
        """
        headers = {"api-key": self.api_key}
        url = f"{self.base_url}/articles/{article_id}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(
                        f"API error {response.status_code} for article {article_id}"
                    )
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching article {article_id}: {e}")
            return None
    
    def parse_markdown(self, markdown: str) -> Tuple[List[Dict], List[Dict], Dict]:
        r"""
        Parse markdown to extract code blocks, links, and metrics
        
        Migrated from: content_collector.py:193-269
        
        Business Logic (STRICT):
        - Code blocks: ```language\ncode\n``` pattern
        - Links: [text](url) pattern
        - Images: ![alt](url) pattern
        - Headings: ^#{1,6}\s+.+$ pattern
        - Link types: anchor (#), internal (dev.to), external (http), relative
        - Word count: Excludes code blocks
        
        Args:
            markdown: Article markdown content
        
        Returns:
            (code_blocks, links, metrics)
        """
        code_blocks = []
        links = []
        
        # Extract code blocks
        # Pattern: ```language\ncode\n```
        code_pattern = r'```(\w+)?\n(.*?)```'
        for i, match in enumerate(re.finditer(code_pattern, markdown, re.DOTALL), 1):
            language = match.group(1) or "text"
            code_text = match.group(2).strip()
            line_count = len(code_text.split('\n'))
            
            code_blocks.append({
                'language': language,
                'code_text': code_text,
                'line_count': line_count,
                'block_order': i
            })
        
        # Extract links
        # Pattern: [text](url)
        link_pattern = r'\[([^\]]+)\]\(([^\)]+)\)'
        for match in re.finditer(link_pattern, markdown):
            link_text = match.group(1)
            url = match.group(2)
            
            # Determine link type
            if url.startswith('#'):
                link_type = 'anchor'
            elif url.startswith('http'):
                if 'dev.to' in url:
                    link_type = 'internal'
                else:
                    link_type = 'external'
            else:
                link_type = 'relative'
            
            links.append({
                'url': url,
                'link_text': link_text,
                'link_type': link_type
            })
        
        # Extract images
        # Pattern: ![alt](url)
        image_pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'
        images_count = len(re.findall(image_pattern, markdown))
        
        # Count headings
        # Pattern: # Heading, ## Heading, etc.
        heading_pattern = r'^#{1,6}\s+.+$'
        headings_count = len(re.findall(heading_pattern, markdown, re.MULTILINE))
        
        # Calculate metrics
        # Remove code blocks for word count (to not count code as words)
        text_without_code = re.sub(code_pattern, '', markdown, flags=re.DOTALL)
        words = text_without_code.split()
        
        metrics = {
            'word_count': len(words),
            'char_count': len(markdown),
            'code_blocks_count': len(code_blocks),
            'links_count': len(links),
            'images_count': images_count,
            'headings_count': headings_count
        }
        
        return code_blocks, links, metrics
    
    async def parse_and_store(
        self,
        article_id: int,
        article_data: Dict,
        conn: AsyncConnection
    ) -> Dict[str, Any]:
        """
        Parse article content and store in database
        
        Migrated from: content_collector.py:271-346
        
        Implementation:
        - Uses ON CONFLICT DO UPDATE for article_content (idempotency)
        - Deletes and re-inserts code_blocks and links (simpler than UPSERT)
        - Single transaction for all inserts
        
        Args:
            article_id: Article ID
            article_data: API response dict with body_markdown, body_html
            conn: Async database connection
        
        Returns:
            Dict with parsing statistics
        """
        from app.db.tables import article_content, article_code_blocks, article_links
        
        markdown = article_data.get('body_markdown', '')
        html = article_data.get('body_html', '')
        
        if not markdown:
            logger.warning(f"No markdown content for article {article_id}")
            return {'error': 'No markdown content'}
        
        # Parse markdown
        code_blocks, links, metrics = self.parse_markdown(markdown)
        timestamp = datetime.now(timezone.utc)
        
        # Insert or update article_content
        stmt = insert(article_content).values(
            article_id=article_id,
            body_markdown=markdown,
            body_html=html,
            word_count=metrics['word_count'],
            char_count=metrics['char_count'],
            code_blocks_count=metrics['code_blocks_count'],
            links_count=metrics['links_count'],
            images_count=metrics['images_count'],
            headings_count=metrics['headings_count'],
            collected_at=timestamp
        )
        
        # ON CONFLICT DO UPDATE
        stmt = stmt.on_conflict_do_update(
            index_elements=['article_id'],
            set_={
                'body_markdown': stmt.excluded.body_markdown,
                'body_html': stmt.excluded.body_html,
                'word_count': stmt.excluded.word_count,
                'char_count': stmt.excluded.char_count,
                'code_blocks_count': stmt.excluded.code_blocks_count,
                'links_count': stmt.excluded.links_count,
                'images_count': stmt.excluded.images_count,
                'headings_count': stmt.excluded.headings_count,
                'collected_at': stmt.excluded.collected_at,
            }
        )
        
        await conn.execute(stmt)
        
        # Delete old code blocks and links (simpler than UPSERT)
        await conn.execute(
            delete(article_code_blocks).where(
                article_code_blocks.c.article_id == article_id
            )
        )
        await conn.execute(
            delete(article_links).where(
                article_links.c.article_id == article_id
            )
        )
        
        # Insert code blocks
        if code_blocks:
            for block in code_blocks:
                await conn.execute(
                    insert(article_code_blocks).values(
                        article_id=article_id,
                        language=block['language'],
                        code_text=block['code_text'],
                        line_count=block['line_count'],
                        block_order=block['block_order']
                    )
                )
        
        # Insert links
        if links:
            for link in links:
                await conn.execute(
                    insert(article_links).values(
                        article_id=article_id,
                        url=link['url'],
                        link_text=link['link_text'],
                        link_type=link['link_type']
                    )
                )
        
        return {
            'article_id': article_id,
            'word_count': metrics['word_count'],
            'code_blocks': len(code_blocks),
            'links': len(links),
            'images': metrics['images_count'],
            'headings': metrics['headings_count']
        }
    
    async def sync_article_content(self, article_id: int) -> Dict[str, Any]:
        """
        Sync content for a single article
        
        Args:
            article_id: Article ID to sync
        
        Returns:
            Dict with sync result
        """
        logger.info(f"Fetching content for article {article_id}...")
        
        # Fetch from API
        article_data = await self.fetch_article_content(article_id)
        
        if not article_data:
            return {
                'article_id': article_id,
                'success': False,
                'error': 'Failed to fetch from API'
            }
        
        # Parse and store
        async with self.engine.begin() as conn:
            try:
                stats = await self.parse_and_store(article_id, article_data, conn)
                logger.info(
                    f"✅ Article {article_id}: {stats['word_count']} words, "
                    f"{stats['code_blocks']} code blocks, {stats['links']} links"
                )
                return {'success': True, **stats}
                
            except Exception as e:
                logger.error(f"Error storing article {article_id}: {e}")
                return {
                    'article_id': article_id,
                    'success': False,
                    'error': str(e)
                }
    
    async def sync_all_content(
        self,
        mode: str = "new",
        specific_id: Optional[int] = None,
        delay: float = 0.5
    ) -> Dict[str, Any]:
        """
        Sync content for multiple articles
        
        Migrated from: content_collector.py:348-407
        
        Args:
            mode: "all" or "new"
            specific_id: Optional specific article ID
            delay: Delay between API calls (seconds)
        
        Returns:
            Dict with summary statistics
        """
        # Get articles to collect
        articles = await self.get_articles_to_collect(mode, specific_id)
        
        if not articles:
            logger.info("No articles to collect")
            return {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'articles': []
            }
        
        logger.info(f"Starting collection for {len(articles)} article(s)...")
        
        successful = 0
        failed = 0
        results = []
        
        for i, article in enumerate(articles, 1):
            article_id = article['article_id']
            title = article['title'][:60] if article['title'] else f"Article {article_id}"
            
            logger.info(f"[{i}/{len(articles)}] {title}...")
            
            result = await self.sync_article_content(article_id)
            results.append(result)
            
            if result['success']:
                successful += 1
            else:
                failed += 1
            
            # Rate limiting
            if i < len(articles):
                await asyncio.sleep(delay)
        
        summary = {
            'total': len(articles),
            'successful': successful,
            'failed': failed,
            'articles': results
        }
        
        logger.info(
            f"Collection complete: {successful} successful, {failed} failed"
        )
        
        return summary


# ============================================================================
# FACTORY AND CLI
# ============================================================================

async def create_content_service(
    api_key: Optional[str] = None,
    engine: Optional[AsyncEngine] = None
) -> ContentService:
    """
    Create ContentService from environment variables
    
    Args:
        api_key: Optional DEV.to API key (reads from env if not provided)
        engine: Optional SQLAlchemy engine
    
    Returns:
        ContentService instance
    """
    if not api_key:
        api_key = os.getenv('DEVTO_API_KEY')
        if not api_key:
            raise ValueError("DEVTO_API_KEY not found in environment")
    
    if engine:
        return ContentService(api_key=api_key, engine=engine)
    
    # Create engine from environment variables
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'devto_analytics')
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD')
    
    if not user or not password:
        raise ValueError(
            "Missing required environment variables: POSTGRES_USER and POSTGRES_PASSWORD"
        )
    
    db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    return ContentService(api_key=api_key, db_url=db_url)


async def main():
    """CLI entry point"""
    import sys
    
    service = await create_content_service()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--collect-all':
            # Collect all articles
            summary = await service.sync_all_content(mode="all")
        elif sys.argv[1] == '--collect-new':
            # Collect only new articles
            summary = await service.sync_all_content(mode="new")
        elif sys.argv[1].startswith('--article='):
            # Collect specific article
            article_id = int(sys.argv[1].split('=')[1])
            summary = await service.sync_all_content(specific_id=article_id)
        else:
            print("Usage:")
            print("  --collect-all     Collect all articles")
            print("  --collect-new     Collect only new articles (default)")
            print("  --article=<id>    Collect specific article")
            return
    else:
        # Default: collect new articles
        summary = await service.sync_all_content(mode="new")
    
    # Print summary
    print("\n" + "="*80)
    print("📊 COLLECTION SUMMARY")
    print("="*80)
    print(f"✅ Successful: {summary['successful']}")
    print(f"❌ Failed: {summary['failed']}")
    print(f"📝 Total: {summary['total']}")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
