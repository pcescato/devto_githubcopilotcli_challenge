#!/usr/bin/env python3
"""
Quality Analytics - Analyze read time, reaction breakdown, and engagement quality
Based on data from /api/analytics/historical endpoint

⚠️ IMPORTANT DATA PERIOD NOTES:
- Read time data: Last 90 days only (from daily_analytics)
- Reaction breakdown (like/unicorn/bookmark): Last 90 days only (from daily_analytics)
- Total reactions/comments: Lifetime (from article_metrics)
- For articles older than 90 days, breakdown will be incomplete
"""

import sqlite3
import argparse
from datetime import datetime, timedelta

class QualityAnalytics:
    def __init__(self, db_path: str = "devto_metrics.db"):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Connect to database"""
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
    
    def show_quality_dashboard(self):
        """Show complete quality metrics dashboard"""
        self.connect()
        
        print("\n" + "="*100)
        print("📊 QUALITY ANALYTICS DASHBOARD")
        print("="*100)
        
        self.show_read_time_analysis()
        self.show_reaction_breakdown()
        self.show_long_tail_champions()
        self.show_quality_scores()
        
        print("\n" + "="*100)
    
    def show_read_time_analysis(self):
        """Analyze average read times per article"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                da.article_id,
                am.title,
                am.reading_time_minutes,
                am.published_at,
                julianday('now') - julianday(am.published_at) as age_days,
                AVG(da.average_read_time_seconds) as avg_read_seconds,
                MAX(da.page_views) as total_views,
                MAX(da.total_read_time_seconds) as total_read_seconds,
                COUNT(DISTINCT da.date) as days_with_data
            FROM daily_analytics da
            JOIN article_metrics am ON da.article_id = am.article_id
            WHERE da.page_views > 0
            GROUP BY da.article_id
            HAVING total_views > 20
            ORDER BY avg_read_seconds DESC
            LIMIT 10
        """)
        
        articles = cursor.fetchall()
        
        print(f"\n\n📖 READ TIME ANALYSIS (Top 10)")
        print("-" * 100)
        print(f"{'Title':<50} {'Length':>8} {'Avg Read':>10} {'Completion':>12} {'Total Hours':>12}")
        print("-" * 100)
        
        for article in articles:
            title = (article['title'][:47] + "...") if len(article['title']) > 50 else article['title']
            length_seconds = (article['reading_time_minutes'] or 0) * 60
            avg_read = article['avg_read_seconds'] or 0
            
            completion = min(100, (avg_read / length_seconds) * 100) if length_seconds > 0 else 0
            total_hours = (article['total_read_seconds'] or 0) / 3600
            
            print(f"{title:<50} {article['reading_time_minutes']:>7}m "
                  f"{int(avg_read):>8}s {completion:>10.1f}% {total_hours:>11.1f}h")
        
        print("\n💡 Note: Read time data covers last 90 days only")
    
    def show_reaction_breakdown(self):
        """Analyze types of reactions with fixed lifetime/breakdown consistency"""
        cursor = self.conn.cursor()
        
        # On utilise MAX(am.reactions) comme source de vérité absolue (Lifetime)
        # Et on fait la somme des colonnes incrémentales de daily_analytics pour le détail
        cursor.execute("""
            SELECT 
                am.article_id,
                am.title,
                am.published_at,
                julianday('now') - julianday(am.published_at) as age_days,
                MAX(am.reactions) as total_reactions_lifetime,
                (
                    SELECT SUM(reactions_like)
                    FROM daily_analytics da2
                    WHERE da2.article_id = am.article_id
                    AND da2.date >= date(am.published_at)
                ) as likes_sum,
                (
                    SELECT SUM(reactions_unicorn)
                    FROM daily_analytics da2
                    WHERE da2.article_id = am.article_id
                    AND da2.date >= date(am.published_at)
                ) as unicorns_sum,
                (
                    SELECT SUM(reactions_readinglist)
                    FROM daily_analytics da2
                    WHERE da2.article_id = am.article_id
                    AND da2.date >= date(am.published_at)
                ) as bookmarks_sum
            FROM article_metrics am
            WHERE am.reactions > 5
            GROUP BY am.article_id
            ORDER BY total_reactions_lifetime DESC
            LIMIT 10
        """)
        
        articles = cursor.fetchall()
        
        print(f"\n\n❤️ REACTION BREAKDOWN (Top 10)")
        print("-" * 120)
        print(f"{'Title':<45} {'Age':>6} {'Lifetime':>10} │ {'Likes':>7} {'🦄':>5} {'📖':>5} {'Sum':>8} {'Gap':>5}")
        print("-" * 120)
        
        for article in articles:
            title = (article['title'][:42] + "...") if len(article['title']) > 45 else article['title']
            age_days = int(article['age_days']) if article['age_days'] else 0
            
            likes = article['likes_sum'] or 0
            unicorns = article['unicorns_sum'] or 0
            bookmarks = article['bookmarks_sum'] or 0
            breakdown_sum = likes + unicorns + bookmarks
            
            # Gap : Différence entre le total réel et la somme du détail (souvent causé par les 90j)
            gap = article['total_reactions_lifetime'] - breakdown_sum
            gap_str = f"{gap:+d}" if gap != 0 else "="
            
            print(f"{title:<45} {age_days:>5}d {article['total_reactions_lifetime']:>10} │ "
                  f"{likes:>7} {unicorns:>5} {bookmarks:>5} {breakdown_sum:>8} {gap_str:>5}")
        
        print("-" * 120)
        print("💡 Gap > 0 : Réactions anciennes (>90j) dont le type (Like/Unicorn) est perdu.")
        print("   Gap < 0 : Réactions retirées par les utilisateurs (historique conservé vs état actuel).")

    def show_quality_scores(self):
        """Calculate quality scores based on consistent 90-day window"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                am.article_id,
                am.title,
                am.reading_time_minutes,
                AVG(da.average_read_time_seconds) as avg_read_seconds,
                MAX(da.page_views) as views_90d,
                (SELECT SUM(reactions_total) FROM daily_analytics da2 WHERE da2.article_id = am.article_id) as reactions_90d,
                (SELECT SUM(comments_total) FROM daily_analytics da2 WHERE da2.article_id = am.article_id) as comments_90d
            FROM article_metrics am
            JOIN daily_analytics da ON am.article_id = da.article_id
            GROUP BY am.article_id
            HAVING views_90d > 20
        """)
        
        articles = cursor.fetchall()
        scored = []
        
        for article in articles:
            length_sec = (article['reading_time_minutes'] or 5) * 60
            avg_read = article['avg_read_seconds'] or 0
            completion = min(100, (avg_read / length_sec) * 100) if length_sec > 0 else 0
            
            # Engagement sur les derniers 90 jours
            engagement = ((article['reactions_90d'] + article['comments_90d']) / article['views_90d']) * 100
            
            # Score pondéré : 70% lecture, 30% engagement (capé à 20% d'engagement)
            score = (completion * 0.7) + (min(engagement, 20) * 1.5)
            scored.append({'title': article['title'], 'score': score, 'completion': completion, 'engagement': engagement})
            
        scored.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"\n\n⭐ QUALITY SCORES (Performance sur 90 jours)")
        print("-" * 100)
        print(f"{'Title':<50} {'Quality':>9} {'Read %':>8} {'Engage %':>10}")
        print("-" * 100)
        
        for art in scored[:10]:
            title = (art['title'][:47] + "...") if len(art['title']) > 50 else art['title']
            print(f"{title:<50} {art['score']:>8.1f} {art['completion']:>7.1f}% {art['engagement']:>9.1f}%")

    def show_long_tail_champions(self):
        """Identifie les articles avec une performance stable (Dédoublonné)"""
        cursor = self.conn.cursor()
        
        # On calcule d'abord la somme des vues par article sans les multiplier par les snapshots
        cursor.execute("""
            SELECT 
                am.title,
                julianday('now') - julianday(am.published_at) as age_days,
                stats.views_30d
            FROM (
                SELECT article_id, SUM(page_views) as views_30d
                FROM daily_analytics
                WHERE date >= date('now', '-30 days')
                GROUP BY article_id
            ) stats
            JOIN (
                SELECT DISTINCT article_id, title, published_at 
                FROM article_metrics
            ) am ON stats.article_id = am.article_id
            WHERE am.published_at < date('now', '-30 days')
            AND stats.views_30d > 20
            ORDER BY stats.views_30d DESC
            LIMIT 10
        """)
        
        articles = cursor.fetchall()
        print(f"\n\n🌟 LONG-TAIL CHAMPIONS (Vues réelles / 30j)")
        print("-" * 80)
        for art in articles:
            title = (art['title'][:50] + "...") if len(art['title']) > 53 else art['title']
            print(f"{title:<53} {int(art['age_days']):>5}d {art['views_30d']:>10} views/30d")

    def analyze_article_daily(self, article_id: int):
        """Show daily breakdown for a specific article"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT title FROM article_metrics WHERE article_id = ?", (article_id,))
        row = cursor.fetchone()
        if not row: return

        print(f"\n📊 DAILY BREAKDOWN: {row['title']}")
        cursor.execute("""
            SELECT date, page_views, average_read_time_seconds, reactions_total 
            FROM daily_analytics WHERE article_id = ? ORDER BY date DESC LIMIT 14
        """, (article_id,))
        print(f"{'Date':<12} {'Views':>7} {'Read(s)':>9} {'Reactions':>10}")
        for d in cursor.fetchall():
            print(f"{d['date']:<12} {d['page_views']:>7} {d['average_read_time_seconds']:>9} {d['reactions_total']:>10}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='devto_metrics.db')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--article', type=int)
    args = parser.parse_args()
    
    qa = QualityAnalytics(args.db)
    qa.connect()
    if args.article: qa.analyze_article_daily(args.article)
    else: qa.show_quality_dashboard()

if __name__ == "__main__":
    main()