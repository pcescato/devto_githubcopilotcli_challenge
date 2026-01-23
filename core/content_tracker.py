#!/usr/bin/env python3
"""
DEV.to Metrics Tracker - Ultimate Edition
Fusion de la collecte riche (originale) et de l'architecture modulaire core.
"""

import argparse
import requests
import json
import time
from datetime import datetime, timezone, timedelta
from core.database import DatabaseManager

class ContentTracker:
    """Détecte les changements de contenu (titre, tags) et logue les milestones."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def check_content_updates(self, article_id, current_title, current_tags, conn=None):
        """
        Compare le contenu actuel avec la dernière version connue.
        Logue un milestone si le titre a changé.
        """
        should_close = conn is None
        if conn is None:
            conn = self.db.get_connection()
        
        # Récupérer la dernière version connue
        cursor = conn.execute("""
            SELECT title, tags FROM article_history 
            WHERE article_id = ? 
            ORDER BY changed_at DESC LIMIT 1
        """, (article_id,))
        last_version = cursor.fetchone()
        
        # Si c'est la première fois ou si quelque chose a changé
        if not last_version or last_version['title'] != current_title or last_version['tags'] != current_tags:
            # Sauvegarder la nouvelle version
            conn.execute("""
                INSERT INTO article_history (article_id, title, tags, changed_at) 
                VALUES (?, ?, ?, ?)
            """, (article_id, current_title, current_tags, datetime.now()))
            
            # Si c'est un changement de titre (événement majeur)
            if last_version and last_version['title'] != current_title:
                description = f"Title change: '{last_version['title']}' → '{current_title}'"
                self.db.log_milestone(article_id, 'title_change', description, conn)
                print(f"📢 {description}")
        
        if should_close:
            conn.commit()
            conn.close()

class DevToTracker:
    def __init__(self, api_key: str, db_path: str = "devto_metrics.db"):
        self.db = DatabaseManager(db_path)
        self.api_key = api_key
        self.headers = {"api-key": api_key}
        self.base_url = "https://dev.to/api"
        self.content_tracker = ContentTracker(self.db)

    def _fetch_articles(self):
        """Récupère tous les articles (publiés et brouillons)."""
        r = requests.get(f"{self.base_url}/articles/me/all", headers=self.headers, params={"per_page": 1000})
        return r.json() if r.status_code == 200 else []

    def collect_standard(self):
        """Collecte de routine : Métriques, Content Tracking, Followers et Commentaires."""
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"📸 Starting standard collection at {timestamp}")
        
        articles = self._fetch_articles()
        if not articles:
            print("❌ No articles found.")
            return

        # 1. Metrics & Content Tracking
        for art in articles:
            if not art.get('published_at'): continue # On track le contenu publié
            
            # Sauvegarde métriques
            self.db.log_article_metrics(art, timestamp)
            
            # Détection de changements (via ContentTracker)
            tags_str = ",".join(art.get('tag_list', []))
            self.content_tracker.check_content_updates(art['id'], art['title'], tags_str)

        # 2. Followers (Snapshot global)
        self._collect_followers(timestamp)
        
        # 3. Commentaires (Synchronisation complète)
        self._collect_comments(articles, timestamp)
        
        print(f"✅ Standard collection complete for {len(articles)} articles.")

    def collect_rich_data(self):
        """Collecte riche : Analytics historiques et Sources de trafic (Referrers)."""
        articles = self._fetch_articles()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        if not articles: return

        print("📊 Starting rich data collection (Historical Analytics & Referrers)...")
        
        for art in articles:
            if not art.get('published_at'): continue
            
            # a) Historical Analytics (Undocumented endpoint)
            self._fetch_historical_analytics(art['id'], timestamp)
            
            # b) Referrers (Undocumented endpoint)
            self._fetch_referrers(art['id'], timestamp)
            
            # Pause pour éviter le rate-limiting
            time.sleep(0.5)

        print("✅ Rich data collection complete.")

    def _collect_followers(self, timestamp):
        """Récupère le compte précis des followers avec pagination."""
        all_followers = []
        page = 1
        while True:
            r = requests.get(f"{self.base_url}/followers/users", 
                             headers=self.headers, params={"per_page": 80, "page": page})
            if r.status_code != 200: break
            data = r.json()
            if not data: break
            all_followers.extend(data)
            page += 1
        
        count = len(all_followers)
        with self.db.get_connection() as conn:
            conn.execute("INSERT INTO follower_events (collected_at, follower_count) VALUES (?, ?)", 
                         (timestamp, count))
        print(f"👥 Total Followers tracked: {count}")

    def _collect_comments(self, articles, timestamp):
        """Récupère et synchronise les commentaires pour chaque article."""
        new_comments = 0
        with self.db.get_connection() as conn:
            for art in articles:
                if not art.get('published_at'): continue
                r = requests.get(f"{self.base_url}/comments", params={"a_id": art['id']})
                if r.status_code == 200:
                    for c in r.json():
                        conn.execute("""
                            INSERT OR IGNORE INTO comments 
                            (comment_id, article_id, author_username, body_html, collected_at, created_at) 
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (c['id_code'], art['id'], c['user']['username'], c['body_html'], timestamp, c['created_at']))
                        if conn.total_changes > 0: new_comments += 1
        print(f"💬 New comments synced: {new_comments}")

    def _fetch_historical_analytics(self, article_id, timestamp):
        """Analytics détaillées (Read time, reactions detail)."""
        r = requests.get(f"{self.base_url}/analytics/historical", 
                         headers=self.headers, params={"article_id": article_id})
        if r.status_code == 200:
            data = r.json()
            with self.db.get_connection() as conn:
                for date_str, s in data.items():
                    conn.execute("""
                        INSERT OR REPLACE INTO daily_analytics 
                        (article_id, date, page_views, average_read_time_seconds, total_read_time_seconds, 
                         reactions_total, reactions_like, reactions_readinglist, reactions_unicorn, 
                         comments_total, follows_total, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (article_id, date_str, s['page_views']['total'], s['page_views']['average_read_time_in_seconds'],
                          s['page_views']['total_read_time_in_seconds'], s['reactions']['total'], s['reactions']['like'],
                          s['reactions']['readinglist'], s['reactions']['unicorn'], s['comments']['total'],
                          s['follows']['total'], timestamp))

    def _fetch_referrers(self, article_id, timestamp):
        """Sources de trafic (Referrers)."""
        r = requests.get(f"{self.base_url}/analytics/referrers", 
                         headers=self.headers, params={"article_id": article_id})
        if r.status_code == 200:
            data = r.json()
            with self.db.get_connection() as conn:
                for ref in data.get('domains', []):
                    conn.execute("""
                        INSERT OR REPLACE INTO referrers (article_id, domain, count, collected_at)
                        VALUES (?, ?, ?, ?)
                    """, (article_id, ref['domain'], ref['count'], timestamp))

def main():
    parser = argparse.ArgumentParser(description='DEV.to Metrics Tracker - Ultimate')
    parser.add_argument('--api-key', required=True, help='API Key')
    parser.add_argument('--collect', action='store_true', help='Standard collection')
    parser.add_argument('--collect-daily', action='store_true', help='Rich analytics & Referrers')
    args = parser.parse_args()

    tracker = DevToTracker(args.api_key)
    if args.collect:
        tracker.collect_standard()
    if args.collect_daily:
        tracker.collect_rich_data()

if __name__ == "__main__":
    main()