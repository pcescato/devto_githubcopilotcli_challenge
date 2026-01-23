#!/usr/bin/env python3
"""
Cleanup utility - Detect and handle deleted articles
Usage: python3 cleanup_articles.py [options]
"""

import sqlite3
import requests
import argparse
from datetime import datetime, timezone
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class ArticleCleanup:
    def __init__(self, api_key: str, db_path: str = "devto_metrics.db"):
        self.api_key = api_key
        self.base_url = "https://dev.to/api"
        self.headers = {"api-key": api_key}
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Connect to database"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
    
    def init_deleted_tracking(self):
        """Add deleted_at column to article_metrics if it doesn't exist"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(article_metrics)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'deleted_at' not in columns:
            print("Adding 'deleted_at' column to article_metrics table...")
            cursor.execute("""
                ALTER TABLE article_metrics 
                ADD COLUMN deleted_at TIMESTAMP
            """)
            self.conn.commit()
            print("✅ Column added")
        
        if 'is_deleted' not in columns:
            print("Adding 'is_deleted' column to article_metrics table...")
            cursor.execute("""
                ALTER TABLE article_metrics 
                ADD COLUMN is_deleted INTEGER DEFAULT 0
            """)
            self.conn.commit()
            print("✅ Column added")
    
    def detect_deleted_articles(self, mark_as_deleted: bool = False):
        """Compare database articles with API to find deleted ones"""
        self.connect()
        
        print("\n🔍 Detecting deleted articles...")
        print("="*80)
        
        # Fetch current articles from API
        print("Fetching current articles from DEV.to API...")
        response = requests.get(
            f"{self.base_url}/articles/me/all",
            headers=self.headers,
            params={"per_page": 1000}
        )
        
        if response.status_code != 200:
            print(f"❌ Error fetching articles: {response.status_code}")
            return
        
        api_articles = response.json()
        api_article_ids = set(article['id'] for article in api_articles)
        
        print(f"✅ Found {len(api_article_ids)} articles on DEV.to")
        
        # Get all article IDs from database
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT article_id, MAX(title) as title
            FROM article_metrics
            WHERE is_deleted IS NULL OR is_deleted = 0
            GROUP BY article_id
        """)
        
        db_articles = cursor.fetchall()
        db_article_ids = set(article['article_id'] for article in db_articles)
        
        print(f"📊 Found {len(db_article_ids)} articles in database (non-deleted)")
        
        # Find deleted articles
        deleted_ids = db_article_ids - api_article_ids
        
        if not deleted_ids:
            print("\n✅ No deleted articles detected!")
            return
        
        print(f"\n⚠️  Found {len(deleted_ids)} deleted articles:")
        print("-"*80)
        
        deleted_articles = []
        for article in db_articles:
            if article['article_id'] in deleted_ids:
                deleted_articles.append(article)
                print(f"   [{article['article_id']}] {article['title']}")
        
        if mark_as_deleted:
            print("\n🗑️  Marking articles as deleted...")
            timestamp = datetime.now(timezone.utc).isoformat()
            
            for article in deleted_articles:
                cursor.execute("""
                    UPDATE article_metrics
                    SET is_deleted = 1, deleted_at = ?
                    WHERE article_id = ?
                """, (timestamp, article['article_id']))
            
            self.conn.commit()
            print(f"✅ Marked {len(deleted_articles)} articles as deleted")
            print("\n💡 These articles will now be filtered out from most reports")
            print("   Use --include-deleted flag to see them in list_articles.py")
        else:
            print("\n💡 Run with --mark-deleted to mark these articles as deleted")
            print("   This will filter them out from reports while keeping historical data")
    
    def list_deleted_articles(self):
        """Show all articles marked as deleted"""
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT
                article_id,
                MAX(title) as title,
                MAX(deleted_at) as deleted_at,
                MAX(views) as last_views,
                MAX(reactions) as last_reactions,
                MAX(comments) as last_comments
            FROM article_metrics
            WHERE is_deleted = 1
            GROUP BY article_id
            ORDER BY deleted_at DESC
        """)
        
        deleted = cursor.fetchall()
        
        if not deleted:
            print("\n✅ No deleted articles in database")
            return
        
        print("\n" + "="*100)
        print(f"🗑️  DELETED ARTICLES ({len(deleted)} total)")
        print("="*100)
        print(f"\n{'ID':<10} {'Title':<50} {'Deleted':<20} {'Last Views':>10}")
        print("-"*100)
        
        for article in deleted:
            title = article['title'][:47] + "..." if len(article['title']) > 50 else article['title']
            deleted_at = article['deleted_at'][:19] if article['deleted_at'] else 'N/A'
            
            print(f"{article['article_id']:<10} {title:<50} {deleted_at:<20} {article['last_views']:>10}")
        
        print("\n💡 To permanently remove deleted articles from database:")
        print("   python3 cleanup_articles.py --api-key YOUR_KEY --purge-deleted")
    
    def purge_deleted_articles(self, confirm: bool = False):
        """Permanently remove deleted articles from database"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Count deleted articles
        cursor.execute("""
            SELECT COUNT(DISTINCT article_id) as count
            FROM article_metrics
            WHERE is_deleted = 1
        """)
        
        count = cursor.fetchone()['count']
        
        if count == 0:
            print("\n✅ No deleted articles to purge")
            return
        
        print(f"\n⚠️  WARNING: This will permanently delete {count} articles from database")
        print("   This includes ALL historical data:")
        print("   - Article metrics")
        print("   - Daily analytics")
        print("   - Comments")
        print("   - Referrers")
        
        if not confirm:
            print("\n❌ Aborted. Use --confirm to proceed")
            return
        
        # Get article IDs to delete
        cursor.execute("""
            SELECT DISTINCT article_id
            FROM article_metrics
            WHERE is_deleted = 1
        """)
        
        article_ids = [row['article_id'] for row in cursor.fetchall()]
        
        print(f"\n🗑️  Purging {len(article_ids)} deleted articles...")
        
        # Delete from all tables
        for article_id in article_ids:
            cursor.execute("DELETE FROM article_metrics WHERE article_id = ?", (article_id,))
            cursor.execute("DELETE FROM daily_analytics WHERE article_id = ?", (article_id,))
            cursor.execute("DELETE FROM comments WHERE article_id = ?", (article_id,))
            cursor.execute("DELETE FROM referrers WHERE article_id = ?", (article_id,))
        
        self.conn.commit()
        print(f"✅ Purged {len(article_ids)} articles from database")
    
    def restore_article(self, article_id: int):
        """Restore a falsely marked deleted article"""
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
            UPDATE article_metrics
            SET is_deleted = 0, deleted_at = NULL
            WHERE article_id = ?
        """, (article_id,))
        
        if cursor.rowcount > 0:
            self.conn.commit()
            print(f"✅ Article {article_id} restored")
        else:
            print(f"❌ Article {article_id} not found or not deleted")
    
    def show_stats(self):
        """Show statistics about articles"""
        self.connect()
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT CASE WHEN is_deleted = 0 OR is_deleted IS NULL THEN article_id END) as active,
                COUNT(DISTINCT CASE WHEN is_deleted = 1 THEN article_id END) as deleted,
                COUNT(DISTINCT article_id) as total
            FROM article_metrics
        """)
        
        stats = cursor.fetchone()
        
        print("\n" + "="*80)
        print("📊 ARTICLE STATISTICS")
        print("="*80)
        print(f"\nActive articles:  {stats['active']}")
        print(f"Deleted articles: {stats['deleted']}")
        print(f"Total articles:   {stats['total']}")
        
        if stats['deleted'] > 0:
            percentage = (stats['deleted'] / stats['total']) * 100
            print(f"\nDeletion rate:    {percentage:.1f}%")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Cleanup utility - Detect and handle deleted articles'
    )
    
    parser.add_argument('--api-key', help='Your Dev.to API key (default: DEVTO_API_KEY env var, required for detection)')
    parser.add_argument('--db', default='devto_metrics.db', help='Database file path')
    parser.add_argument('--init', action='store_true', help='Initialize deleted tracking (add columns)')
    parser.add_argument('--detect', action='store_true', help='Detect deleted articles')
    parser.add_argument('--mark-deleted', action='store_true', help='Mark detected articles as deleted')
    parser.add_argument('--list-deleted', action='store_true', help='List deleted articles')
    parser.add_argument('--purge-deleted', action='store_true', help='Permanently remove deleted articles')
    parser.add_argument('--confirm', action='store_true', help='Confirm destructive operations')
    parser.add_argument('--restore', type=int, metavar='ID', help='Restore article by ID')
    parser.add_argument('--stats', action='store_true', help='Show article statistics')
    
    args = parser.parse_args()
    
    # Get API key from argument or environment variable
    api_key = args.api_key or os.getenv('DEVTO_API_KEY', '')
    
    # API key required for some operations
    if args.detect or args.mark_deleted:
        if not api_key:
            print("❌ Error: DEVTO_API_KEY not found for detection operations")
            print("   Set it via: --api-key YOUR_KEY or environment variable DEVTO_API_KEY")
            return
    
    cleanup = ArticleCleanup(api_key, args.db)
    
    if args.init:
        cleanup.init_deleted_tracking()
    
    if args.detect or args.mark_deleted:
        cleanup.detect_deleted_articles(mark_as_deleted=args.mark_deleted)
    
    if args.list_deleted:
        cleanup.list_deleted_articles()
    
    if args.purge_deleted:
        cleanup.purge_deleted_articles(confirm=args.confirm)
    
    if args.restore:
        cleanup.restore_article(args.restore)
    
    if args.stats:
        cleanup.show_stats()
    
    cleanup.close()


if __name__ == "__main__":
    main()