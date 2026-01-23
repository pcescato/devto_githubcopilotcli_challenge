#!/usr/bin/env python3
import os
import requests
import json
import argparse
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from core.database import DatabaseManager
from core.content_tracker import ContentTracker

load_dotenv()

class DevToTracker:
    def __init__(self, api_key, db_path="devto_metrics.db"):
        self.api_key = api_key
        self.headers = {"api-key": api_key}
        self.base_url = "https://dev.to/api"
        self.db = DatabaseManager(db_path)
        self.content_tracker = ContentTracker(self.db)

    def fetch_api_articles(self):
        """Récupération brute depuis l'API Dev.to."""
        url = f"{self.base_url}/articles/me/all"
        response = requests.get(url, headers=self.headers, params={"per_page": 1000})
        response.raise_for_status()
        return response.json()

    def collect_snapshot(self):
        """Collection standard : Métriques de base."""
        articles = self.fetch_api_articles()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        print(f"📡 Start collection: {len(articles)} articles found.")
        
        conn = self.db.get_connection()
        for art in articles:
            # 1. Insertion du Snapshot (article_metrics)
            conn.execute("""
                INSERT INTO article_metrics 
                (collected_at, article_id, title, slug, published_at, views, reactions, comments, reading_time_minutes, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, art['id'], art['title'], art['slug'], 
                art['published_at'], art['page_views_count'], 
                art['public_reactions_count'], art['comments_count'],
                art['reading_time_minutes'], json.dumps(art['tag_list'])
            ))

            # 2. Tracking automatique des modifications (Titre, etc.)
            if art.get('published_at'):  # Seulement pour articles publiés
                tags_str = ",".join(art.get('tag_list', []))
                self.content_tracker.check_content_updates(
                    art['id'], art['title'], tags_str, conn
                )
        
        conn.commit()
        conn.close()
        print(f"✅ Data stored and content checked.")

    def collect_full(self):
        """Collection complète : Métriques + Followers + Commentaires."""
        articles = self.fetch_api_articles()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        print(f"📡 Full collection starting: {len(articles)} articles found.")
        
        # 1. Métriques + Content Tracking
        self.collect_snapshot()
        
        # 2. Followers
        self._collect_followers(timestamp)
        
        # 3. Commentaires
        self._collect_comments(articles, timestamp)
        
        print(f"✅ Full collection complete.")

    def collect_rich_analytics(self):
        """Collection riche : Analytics historiques + Referrers (endpoints non documentés)."""
        articles = self.fetch_api_articles()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        print(f"📊 Rich analytics collection starting...")
        
        for art in articles:
            if not art.get('published_at'):
                continue
            
            # Analytics historiques
            self._fetch_historical_analytics(art['id'], timestamp)
            
            # Referrers (sources de trafic)
            self._fetch_referrers(art['id'], timestamp)
            
            # Pause pour éviter rate limiting
            time.sleep(0.5)
        
        print(f"✅ Rich analytics collection complete.")

    def collect_all(self):
        """Run full collection (metrics+followers+comments) then rich analytics."""
        # collect_full inclut collect_snapshot
        self.collect_full()
        self.collect_rich_analytics()

    def _collect_followers(self, timestamp):
        """Récupère le compte précis des followers avec pagination."""
        print(f"👥 Collecting followers...")
        all_followers = []
        page = 1
        
        while True:
            r = requests.get(
                f"{self.base_url}/followers/users",
                headers=self.headers,
                params={"per_page": 80, "page": page}
            )
            if r.status_code != 200:
                break
            
            data = r.json()
            if not data:
                break
            
            all_followers.extend(data)
            page += 1
        
        count = len(all_followers)
        conn = self.db.get_connection()
        
        # Calcul du delta avec la dernière valeur
        cursor = conn.execute("""
            SELECT follower_count FROM follower_events 
            ORDER BY collected_at DESC LIMIT 1
        """)
        last = cursor.fetchone()
        delta = count - last['follower_count'] if last else 0
        
        conn.execute("""
            INSERT INTO follower_events (collected_at, follower_count, new_followers_since_last) 
            VALUES (?, ?, ?)
        """, (timestamp, count, delta))
        
        conn.commit()
        conn.close()
        print(f"👥 Followers: {count} (Δ{delta:+d})")

    def _collect_comments(self, articles, timestamp):
        """Récupère et synchronise les commentaires pour chaque article."""
        print(f"💬 Collecting comments...")
        new_comments = 0
        
        conn = self.db.get_connection()
        for art in articles:
            if not art.get('published_at'):
                continue
            
            r = requests.get(f"{self.base_url}/comments", params={"a_id": art['id']})
            if r.status_code == 200:
                for c in r.json():
                    body_text = c.get('body_html', '')
                    user = c.get('user', {})
                    cursor = conn.execute("""
                        INSERT OR IGNORE INTO comments 
                        (comment_id, article_id, article_title, author_username, author_name, 
                         body_html, body_length, created_at, collected_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        c['id_code'], art['id'], art['title'],
                        user.get('username'), user.get('name'),
                        body_text, len(body_text), c['created_at'], timestamp
                    ))
                    if cursor.rowcount > 0:
                        new_comments += 1
        
        conn.commit()
        conn.close()
        print(f"💬 New comments: {new_comments}")

    def _fetch_historical_analytics(self, article_id, timestamp):
        """Analytics détaillées quotidiennes (endpoint non documenté)."""
        r = requests.get(
            f"{self.base_url}/analytics/historical",
            headers=self.headers,
            params={"article_id": article_id}
        )
        
        if r.status_code == 200:
            data = r.json()
            conn = self.db.get_connection()
            
            for date_str, stats in data.items():
                conn.execute("""
                    INSERT OR REPLACE INTO daily_analytics 
                    (article_id, date, page_views, average_read_time_seconds, total_read_time_seconds,
                     reactions_total, reactions_like, reactions_readinglist, reactions_unicorn,
                     comments_total, follows_total, collected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    article_id, date_str,
                    stats['page_views']['total'],
                    stats['page_views'].get('average_read_time_in_seconds', 0),
                    stats['page_views'].get('total_read_time_in_seconds', 0),
                    stats['reactions']['total'],
                    stats['reactions'].get('like', 0),
                    stats['reactions'].get('readinglist', 0),
                    stats['reactions'].get('unicorn', 0),
                    stats['comments']['total'],
                    stats['follows']['total'],
                    timestamp
                ))
            
            conn.commit()
            conn.close()

    def _fetch_referrers(self, article_id, timestamp):
        """Sources de trafic (endpoint non documenté)."""
        r = requests.get(
            f"{self.base_url}/analytics/referrers",
            headers=self.headers,
            params={"article_id": article_id}
        )
        
        if r.status_code == 200:
            data = r.json()
            conn = self.db.get_connection()
            
            for ref in data.get('domains', []):
                conn.execute("""
                    INSERT OR REPLACE INTO referrers 
                    (article_id, domain, count, collected_at)
                    VALUES (?, ?, ?, ?)
                """, (article_id, ref['domain'], ref['count'], timestamp))
            
            conn.commit()
            conn.close()

def main():
    parser = argparse.ArgumentParser(description='Dev.to Tracker - Full Feature Edition')
    parser.add_argument('--collect', action='store_true', 
                       help='Standard collection (metrics + content tracking)')
    parser.add_argument('--full', action='store_true',
                       help='Full collection (metrics + followers + comments)')
    parser.add_argument('--rich', action='store_true',
                       help='Rich analytics (historical data + referrers)')
    parser.add_argument('--all', action='store_true',
                        help='Run full collection then rich analytics (everything)')
    args = parser.parse_args()

    api_key = os.getenv('DEVTO_API_KEY')
    if not api_key:
        print("❌ Error: DEVTO_API_KEY environment variable not set.")
        return

    tracker = DevToTracker(api_key)
    
    if args.collect:
        tracker.collect_snapshot()
    elif args.full:
        tracker.collect_full()
    elif args.rich:
        tracker.collect_rich_analytics()
    elif args.all:
        tracker.collect_all()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()