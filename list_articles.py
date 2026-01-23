#!/usr/bin/env python3
"""
List Articles - Utility to list articles using the centralized DatabaseManager
Usage: python3 list_articles.py [options]
"""

import argparse
import json
from core.database import DatabaseManager

class ArticleLister:
    def __init__(self, db_path: str = "devto_metrics.db"):
        # On utilise le Master Controller pour toute la gestion DB
        self.db = DatabaseManager(db_path)
    
    def list_all_articles(self, sort_by: str = "published", limit: int = None, include_deleted: bool = False):
        """List all articles using DatabaseManager methods"""
        
        # Récupération des articles via le Controller
        # DatabaseManager s'occupe de la migration et de la requête propre
        articles = self.db.get_all_active_articles()
        
        if not articles:
            print("\n❌ No articles found in database")
            print("Run: python3 devto_tracker.py --collect")
            return
        
        status_msg = "active only"
        
        print("\n" + "="*100)
        print(f"📚 YOUR ARTICLES (Total: {len(articles)}, {status_msg})")
        print("="*100)
        print(f"\n{'ID':<10} {'Title':<50} {'Published':<12} {'Views':>10}")
        print("-"*100)
        
        for article in articles:
            # Gestion de la longueur du titre
            display_title = article['title'][:47] + "..." if len(article['title']) > 50 else article['title']
            
            # Gestion de la date de publication
            pub_date = article['published_at'][:10] if article['published_at'] else 'N/A'
            
            # Affichage de la ligne
            print(f"{article['article_id']:<10} {display_title:<50} {pub_date:<12} {article['total_views']:>10,}")
        
        print("\n💡 Use article ID with other commands:")
        print("   python3 sismograph.py --article <ID>")
        print("   python3 nlp_analyzer.py --article <ID>")

    def show_article_details(self, article_id: int):
        """Show detailed info for specific article using the Controller"""
        article = self.db.get_latest_article_snapshot(article_id)
        
        if not article:
            print(f"\n❌ Article {article_id} not found")
            return
        
        print("\n" + "="*100)
        print(f"📄 ARTICLE DETAILS")
        print("="*100)
        print(f"\nID:           {article['article_id']}")
        print(f"Title:        {article['title']}")
        print(f"Slug:         {article['slug']}")
        print(f"Published:    {article['published_at'][:19] if article['published_at'] else 'N/A'}")
        
        if article['tags']:
            try:
                tags = json.loads(article['tags'])
                print(f"Tags:         {', '.join(tags)}")
            except:
                print(f"Tags:         {article['tags']}")
        
        print(f"\n📊 CURRENT METRICS:")
        print(f"Views:        {article['views']:,}")
        print(f"Reactions:    {article['reactions']:,}")
        print(f"Comments:     {article['comments']:,}")
        
        print(f"\n🔗 DEV.TO URL:")
        print(f"   https://dev.to/{article['slug']}")

def main():
    parser = argparse.ArgumentParser(
        description='List Articles - Powered by core.database'
    )
    
    parser.add_argument('--db', default='devto_metrics.db', help='Database file path')
    parser.add_argument('--all', action='store_true', help='List all articles (default)')
    parser.add_argument('--id', type=int, metavar='ID', help='Show details for specific article')
    parser.add_argument('--limit', type=int, metavar='N', help='Limit number of results')
    
    args = parser.parse_args()
    
    lister = ArticleLister(args.db)
    
    if args.id:
        lister.show_article_details(args.id)
    else:
        # Par défaut, on liste tout
        lister.list_all_articles(limit=args.limit)

if __name__ == "__main__":
    main()