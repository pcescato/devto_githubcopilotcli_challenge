#!/usr/bin/env python3
"""
DEV.to Content Collector
Collects article content (markdown, code blocks, links) for future NLP analysis

Usage:
    python3 content_collector.py --collect-all    # First run: get all articles
    python3 content_collector.py --collect-new    # Subsequent: only new articles
    python3 content_collector.py --article 123    # Specific article
"""

import requests
import argparse
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import os
import time
from dotenv import load_dotenv

# Import DatabaseManager from core
from core.database import DatabaseManager

# Load environment variables from .env file
load_dotenv()

class ContentCollector:
    def __init__(self, api_key: str, db_path: str = "devto_metrics.db"):
        self.api_key = api_key
        self.db_manager = DatabaseManager(db_path)
        self.base_url = "https://dev.to/api"
        self.headers = {"api-key": api_key}
    
    def init_db(self):
        """Initialize database with content tables"""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        print("📊 Creating content tables if they don't exist...")
        
        # Table 1: Article content
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_content (
                article_id INTEGER PRIMARY KEY,
                body_markdown TEXT NOT NULL,
                body_html TEXT,
                
                -- Basic metrics
                word_count INTEGER,
                char_count INTEGER,
                code_blocks_count INTEGER,
                links_count INTEGER,
                images_count INTEGER,
                headings_count INTEGER,
                
                -- Metadata
                collected_at TIMESTAMP NOT NULL,
                
                FOREIGN KEY (article_id) REFERENCES article_metrics(article_id)
            )
        """)
        
        # Table 2: Code blocks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_code_blocks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                language TEXT,
                code_text TEXT,
                line_count INTEGER,
                block_order INTEGER,
                
                FOREIGN KEY (article_id) REFERENCES article_metrics(article_id)
            )
        """)
        
        # Table 3: Links
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                link_text TEXT,
                link_type TEXT,
                
                FOREIGN KEY (article_id) REFERENCES article_metrics(article_id)
            )
        """)
        
        # Indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_code_blocks_article 
            ON article_code_blocks(article_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_links_article 
            ON article_links(article_id)
        """)
        
        conn.commit()
        conn.close()
        print("✅ Tables created/verified")
    
    def get_articles_to_collect(self, mode: str = "new", specific_id: Optional[int] = None) -> List[int]:
        """
        Get list of article IDs to collect content for
        
        Args:
            mode: "all" (all articles), "new" (not yet collected), "specific" (one article)
            specific_id: Article ID for specific mode
        
        Returns:
            List of article IDs
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        if specific_id:
            # Check if article exists
            cursor.execute("""
                SELECT article_id FROM article_metrics WHERE article_id = ?
            """, (specific_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return [specific_id]
            else:
                print(f"⚠️  Article {specific_id} not found in database")
                return []
        
        elif mode == "all":
            # Get all articles
            cursor.execute("""
                SELECT DISTINCT article_id 
                FROM article_metrics 
                WHERE published_at IS NOT NULL
                ORDER BY article_id
            """)
            
            articles = [row['article_id'] for row in cursor.fetchall()]
            conn.close()
            print(f"📚 Found {len(articles)} total articles")
            return articles
        
        elif mode == "new":
            # Get articles not yet in article_content
            cursor.execute("""
                SELECT DISTINCT am.article_id 
                FROM article_metrics am
                LEFT JOIN article_content ac ON am.article_id = ac.article_id
                WHERE am.published_at IS NOT NULL
                AND ac.article_id IS NULL
                ORDER BY am.article_id
            """)
            
            articles = [row['article_id'] for row in cursor.fetchall()]
            conn.close()
            print(f"📝 Found {len(articles)} new articles (not yet collected)")
            return articles
        
        else:
            conn.close()
            print(f"❌ Unknown mode: {mode}")
            return []
    
    def fetch_article_content(self, article_id: int) -> Optional[Dict]:
        """
        Fetch article content from DEV.to API
        
        Returns:
            Dict with markdown, html, etc. or None if error
        """
        try:
            response = requests.get(
                f"{self.base_url}/articles/{article_id}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"  ⚠️  API error {response.status_code} for article {article_id}")
                return None
                
        except Exception as e:
            print(f"  ❌ Error fetching article {article_id}: {e}")
            return None
    
    def parse_markdown(self, markdown: str) -> Tuple[List[Dict], List[Dict], Dict]:
        """
        Parse markdown to extract:
        - Code blocks
        - Links
        - Basic metrics
        
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
    
    def save_article_content(self, article_id: int, article_data: Dict):
        """
        Save article content to database
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        markdown = article_data.get('body_markdown', '')
        html = article_data.get('body_html', '')
        
        if not markdown:
            print(f"  ⚠️  No markdown content for article {article_id}")
            conn.close()
            return
        
        # Parse markdown
        code_blocks, links, metrics = self.parse_markdown(markdown)
        
        # Save main content
        cursor.execute("""
            INSERT OR REPLACE INTO article_content
            (article_id, body_markdown, body_html, word_count, char_count,
             code_blocks_count, links_count, images_count, headings_count, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            article_id,
            markdown,
            html,
            metrics['word_count'],
            metrics['char_count'],
            metrics['code_blocks_count'],
            metrics['links_count'],
            metrics['images_count'],
            metrics['headings_count'],
            timestamp
        ))
        
        # Delete old code blocks and links (in case of re-collection)
        cursor.execute("DELETE FROM article_code_blocks WHERE article_id = ?", (article_id,))
        cursor.execute("DELETE FROM article_links WHERE article_id = ?", (article_id,))
        
        # Save code blocks
        for block in code_blocks:
            cursor.execute("""
                INSERT INTO article_code_blocks
                (article_id, language, code_text, line_count, block_order)
                VALUES (?, ?, ?, ?, ?)
            """, (
                article_id,
                block['language'],
                block['code_text'],
                block['line_count'],
                block['block_order']
            ))
        
        # Save links
        for link in links:
            cursor.execute("""
                INSERT INTO article_links
                (article_id, url, link_text, link_type)
                VALUES (?, ?, ?, ?)
            """, (
                article_id,
                link['url'],
                link['link_text'],
                link['link_type']
            ))
        
        conn.commit()
        conn.close()
        
        # Print summary
        print(f"  ✅ Saved: {metrics['word_count']} words, "
              f"{metrics['code_blocks_count']} code blocks, "
              f"{metrics['links_count']} links")
    
    def collect_articles(self, article_ids: List[int]):
        """
        Collect content for a list of articles
        """
        if not article_ids:
            print("📭 No articles to collect")
            return
        
        print(f"\n🚀 Starting collection for {len(article_ids)} article(s)...")
        print("=" * 80)
        
        successful = 0
        failed = 0
        
        for i, article_id in enumerate(article_ids, 1):
            # Get article title for nicer display
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT title FROM article_metrics 
                WHERE article_id = ? 
                LIMIT 1
            """, (article_id,))
            
            row = cursor.fetchone()
            conn.close()
            title = row['title'][:60] if row else f"Article {article_id}"
            
            print(f"\n[{i}/{len(article_ids)}] {title}...")
            print(f"  📥 Fetching content from API...")
            
            # Fetch from API
            article_data = self.fetch_article_content(article_id)
            
            if article_data:
                # Save to database
                try:
                    self.save_article_content(article_id, article_data)
                    successful += 1
                except Exception as e:
                    print(f"  ❌ Error saving: {e}")
                    failed += 1
            else:
                failed += 1
            
            # Small delay to be nice to API
            time.sleep(0.5)
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 COLLECTION SUMMARY")
        print("=" * 80)
        print(f"✅ Successful: {successful}")
        print(f"❌ Failed:     {failed}")
        print(f"📦 Total:      {len(article_ids)}")
    
    def show_stats(self):
        """Show statistics about collected content"""
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()
        
        print("\n" + "=" * 80)
        print("📊 CONTENT DATABASE STATISTICS")
        print("=" * 80)
        
        # Total articles with content
        cursor.execute("SELECT COUNT(*) as count FROM article_content")
        total = cursor.fetchone()['count']
        print(f"\n📚 Articles with content: {total}")
        
        # Total words
        cursor.execute("SELECT SUM(word_count) as total FROM article_content")
        total_words = cursor.fetchone()['total'] or 0
        print(f"📝 Total words: {total_words:,}")
        
        # Total code blocks
        cursor.execute("SELECT COUNT(*) as count FROM article_code_blocks")
        total_code = cursor.fetchone()['count']
        print(f"💻 Total code blocks: {total_code}")
        
        # Languages used
        cursor.execute("""
            SELECT language, COUNT(*) as count 
            FROM article_code_blocks 
            GROUP BY language 
            ORDER BY count DESC 
            LIMIT 10
        """)
        
        languages = cursor.fetchall()
        if languages:
            print(f"\n🔤 Top languages:")
            for lang in languages:
                print(f"   {lang['language']:<15} {lang['count']:>4} blocks")
        
        # Total links
        cursor.execute("SELECT COUNT(*) as count FROM article_links")
        total_links = cursor.fetchone()['count']
        print(f"\n🔗 Total links: {total_links}")
        
        # Link types
        cursor.execute("""
            SELECT link_type, COUNT(*) as count 
            FROM article_links 
            GROUP BY link_type 
            ORDER BY count DESC
        """)
        
        link_types = cursor.fetchall()
        if link_types:
            print(f"\n🔗 Link types:")
            for lt in link_types:
                print(f"   {lt['link_type']:<15} {lt['count']:>4} links")
        
        # Average article length
        cursor.execute("SELECT AVG(word_count) as avg FROM article_content")
        avg_words = cursor.fetchone()['avg'] or 0
        print(f"\n📏 Average article length: {int(avg_words)} words")
        
        # Longest and shortest
        cursor.execute("""
            SELECT ac.article_id, am.title, ac.word_count
            FROM article_content ac
            JOIN article_metrics am ON ac.article_id = am.article_id
            ORDER BY ac.word_count DESC
            LIMIT 1
        """)
        
        longest = cursor.fetchone()
        if longest:
            print(f"\n📖 Longest article: {longest['title'][:50]}... ({longest['word_count']} words)")
        
        cursor.execute("""
            SELECT ac.article_id, am.title, ac.word_count
            FROM article_content ac
            JOIN article_metrics am ON ac.article_id = am.article_id
            ORDER BY ac.word_count ASC
            LIMIT 1
        """)
        
        shortest = cursor.fetchone()
        if shortest:
            print(f"📄 Shortest article: {shortest['title'][:50]}... ({shortest['word_count']} words)")
        
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Collect DEV.to article content for NLP analysis'
    )
    
    parser.add_argument('--api-key', help='DEV.to API key (default: DEVTO_API_KEY env var)')
    parser.add_argument('--db', default='devto_metrics.db', help='Database path')
    
    # Collection modes
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument('--collect-all', action='store_true',
                           help='Collect ALL articles (first run)')
    mode_group.add_argument('--collect-new', action='store_true',
                           help='Collect only NEW articles (not yet in DB)')
    mode_group.add_argument('--article', type=int, metavar='ID',
                           help='Collect specific article by ID')
    
    parser.add_argument('--stats', action='store_true',
                       help='Show statistics after collection')
    
    args = parser.parse_args()
    
    # Get API key from argument or environment variable
    api_key = args.api_key or os.getenv('DEVTO_API_KEY')
    
    if not api_key:
        print("❌ Error: DEVTO_API_KEY not found")
        print("   Set it via: --api-key YOUR_KEY or environment variable DEVTO_API_KEY")
        return
    
    print("=" * 80)
    print("📚 DEV.to Content Collector")
    print("=" * 80)
    
    collector = ContentCollector(api_key, args.db)
    
    try:
        # Initialize database
        collector.init_db()
        
        # Determine mode
        if args.collect_all:
            mode = "all"
            specific_id = None
        elif args.collect_new:
            mode = "new"
            specific_id = None
        elif args.article:
            mode = "specific"
            specific_id = args.article
        
        # Get articles to collect
        article_ids = collector.get_articles_to_collect(mode, specific_id)
        
        # Collect
        collector.collect_articles(article_ids)
        
        # Show stats
        if args.stats or mode == "all":
            collector.show_stats()
        
        print("\n" + "=" * 80)
        print("✅ Collection complete!")
        print("=" * 80)
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
