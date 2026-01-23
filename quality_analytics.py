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
            title = article['title'][:47] + "..." if len(article['title']) > 50 else article['title']
            length_seconds = (article['reading_time_minutes'] or 0) * 60
            avg_read = article['avg_read_seconds'] or 0
            
            # Completion rate (how much of the article they read)
            completion = 0
            if length_seconds > 0:
                completion = (avg_read / length_seconds) * 100
                completion = min(100, completion)  # Cap at 100%
            
            total_hours = (article['total_read_seconds'] or 0) / 3600
            
            print(f"{title:<50} {article['reading_time_minutes']:>7}m "
                  f"{int(avg_read):>8}s {completion:>10.1f}% {total_hours:>11.1f}h")
        
        print("\n💡 Note: Read time data covers last 90 days only")
    
    def show_reaction_breakdown(self):
        """Analyze types of reactions"""
        cursor = self.conn.cursor()
        
        # FIXED: daily_analytics contains INCREMENTAL data (new reactions per day)
        # NOT cumulative! We need to SUM, not MAX
        # BUT: Only sum from publication date onwards (ignore draft period)
        cursor.execute("""
            SELECT 
                am.article_id,
                am.title,
                am.published_at,
                julianday('now') - julianday(am.published_at) as age_days,
                MAX(am.reactions) as total_reactions_lifetime,
                MAX(am.comments) as total_comments_lifetime,
                (
                    SELECT SUM(reactions_like)
                    FROM daily_analytics da2
                    WHERE da2.article_id = am.article_id
                    AND da2.date >= date(am.published_at)
                ) as reactions_like_since_pub,
                (
                    SELECT SUM(reactions_unicorn)
                    FROM daily_analytics da2
                    WHERE da2.article_id = am.article_id
                    AND da2.date >= date(am.published_at)
                ) as reactions_unicorn_since_pub,
                (
                    SELECT SUM(reactions_readinglist)
                    FROM daily_analytics da2
                    WHERE da2.article_id = am.article_id
                    AND da2.date >= date(am.published_at)
                ) as reactions_bookmark_since_pub,
                (
                    SELECT SUM(reactions_like) + SUM(reactions_unicorn) + SUM(reactions_readinglist)
                    FROM daily_analytics da2
                    WHERE da2.article_id = am.article_id
                    AND da2.date >= date(am.published_at)
                ) as reactions_breakdown_sum
            FROM article_metrics am
            WHERE am.reactions > 5
            GROUP BY am.article_id
            ORDER BY total_reactions_lifetime DESC
            LIMIT 10
        """)
        
        articles = cursor.fetchall()
        
        print(f"\n\n❤️ REACTION BREAKDOWN (Top 10 by lifetime reactions)")
        print("-" * 120)
        print(f"{'Title':<45} {'Age':>6} {'Lifetime':>10} │ {'Likes':>7} {'🦄':>5} {'📖':>5} {'Sum':>8} {'Gap':>5}")
        print("-" * 120)
        
        for article in articles:
            title = article['title'][:42] + "..." if len(article['title']) > 45 else article['title']
            age_days = int(article['age_days']) if article['age_days'] else 0
            
            age_indicator = f"{age_days}d"
            
            # Use breakdown sum (more reliable than reactions_total)
            likes = article['reactions_like_since_pub'] or 0
            unicorns = article['reactions_unicorn_since_pub'] or 0
            bookmarks = article['reactions_bookmark_since_pub'] or 0
            breakdown_sum = article['reactions_breakdown_sum'] or 0
            
            # Gap = difference between lifetime and breakdown sum
            gap = article['total_reactions_lifetime'] - breakdown_sum
            gap_str = f"{gap:+d}" if gap != 0 else "="
            
            print(f"{title:<45} {age_indicator:>6} {article['total_reactions_lifetime']:>10} │ "
                  f"{likes:>7} "
                  f"{unicorns:>5} "
                  f"{bookmarks:>5} "
                  f"{breakdown_sum:>8} {gap_str:>5}")
        
        print("-" * 120)
        print("💡 Lifetime = total reactions from public API (current state)")
        print("   Sum = SUM(likes + unicorns + bookmarks) since publication")
        print("   Gap = Lifetime - Sum")
        print("   ")
        print("   ⚠️ If Sum > Lifetime (Gap negative):")
        print("      → Some people unliked/removed their reactions")
        print("      → History keeps original actions, lifetime shows current count")
        print("   ")
        print("   ⚠️ If Lifetime > Sum (Gap positive):")
        print("      → Recent reactions not yet in daily_analytics (sync delay)")
        print("      → Or reactions of types not in breakdown (rare)")
        
        # Show reaction patterns (only for articles with complete data)
        print("\n💡 Reaction Patterns (articles ≤90 days old only):")
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN reactions_unicorn * 1.0 / NULLIF(reactions_total, 0) > 0.3 
                        THEN 'High Unicorn (Excitement)'
                    WHEN reactions_readinglist * 1.0 / NULLIF(reactions_total, 0) > 0.4 
                        THEN 'High Bookmark (Value)'
                    ELSE 'Standard (Likes)'
                END as pattern,
                COUNT(*) as articles
            FROM (
                SELECT 
                    am.article_id,
                    julianday('now') - julianday(am.published_at) as age_days,
                    MAX(da.reactions_total) as reactions_total,
                    MAX(da.reactions_like) as reactions_like,
                    MAX(da.reactions_unicorn) as reactions_unicorn,
                    MAX(da.reactions_readinglist) as reactions_readinglist
                FROM article_metrics am
                LEFT JOIN daily_analytics da ON am.article_id = da.article_id
                WHERE am.reactions > 5
                AND julianday('now') - julianday(am.published_at) <= 90
                GROUP BY am.article_id
            )
            GROUP BY pattern
        """)
        
        for row in cursor.fetchall():
            print(f"  • {row['pattern']}: {row['articles']} articles")
    
    def show_long_tail_champions(self):
        """Identify articles with strong long-tail performance"""
        cursor = self.conn.cursor()
        
        # Get articles with views 30+ days after publication
        cursor.execute("""
            SELECT 
                da.article_id,
                am.title,
                am.published_at,
                MAX(CASE WHEN da.date >= date('now', '-30 days') THEN da.page_views ELSE 0 END) as recent_views,
                MAX(CASE WHEN da.date < date('now', '-30 days') AND da.date >= date('now', '-90 days') THEN da.page_views ELSE 0 END) as older_views,
                julianday('now') - julianday(am.published_at) as days_since_publication
            FROM daily_analytics da
            JOIN (
                SELECT DISTINCT article_id, title, published_at
                FROM article_metrics
                WHERE published_at IS NOT NULL
            ) am ON da.article_id = am.article_id
            WHERE am.published_at < date('now', '-30 days')
            GROUP BY da.article_id
            HAVING recent_views > 50
            ORDER BY recent_views DESC
            LIMIT 10
        """)
        
        articles = cursor.fetchall()
        
        print(f"\n\n🌟 LONG-TAIL CHAMPIONS (Recent views on old articles)")
        print("-" * 100)
        print(f"{'Title':<50} {'Age':>8} {'Last 30d':>10} {'30-90d':>10} {'Trend':>8}")
        print("-" * 100)
        
        for article in articles:
            title = article['title'][:47] + "..." if len(article['title']) > 50 else article['title']
            age_days = int(article['days_since_publication'])
            recent = article['recent_views']
            older = article['older_views'] or 0
            
            # Calculate trend
            if older > 0:
                trend_pct = ((recent - older) / older) * 100
                trend = f"{trend_pct:+.0f}%"
            else:
                trend = "NEW"
            
            print(f"{title:<50} {age_days:>7}d {recent:>10} {older:>10} {trend:>8}")
    
    def show_quality_scores(self):
        """Calculate and display quality scores"""
        cursor = self.conn.cursor()
        
        # FIXED: Use consistent data periods and document clearly
        # Use daily_analytics data only (consistent 90-day period for all metrics)
        cursor.execute("""
            SELECT 
                am.article_id,
                am.title,
                am.reading_time_minutes,
                am.published_at,
                julianday('now') - julianday(am.published_at) as age_days,
                AVG(da.average_read_time_seconds) as avg_read_seconds,
                MAX(da.page_views) as views_90d,
                MAX(da.reactions_total) as reactions_90d,
                MAX(da.comments_total) as comments_90d,
                COUNT(DISTINCT da.date) as days_with_data
            FROM article_metrics am
            LEFT JOIN daily_analytics da ON am.article_id = da.article_id
            WHERE da.page_views > 0
            GROUP BY am.article_id
            HAVING views_90d > 20
        """)
        
        articles = cursor.fetchall()
        
        # Calculate quality scores
        scored_articles = []
        for article in articles:
            length_seconds = (article['reading_time_minutes'] or 7) * 60
            avg_read = article['avg_read_seconds'] or 0
            views = article['views_90d'] or 1
            
            # Completion rate (0-100)
            completion = min(100, (avg_read / length_seconds) * 100) if length_seconds > 0 else 0
            
            # Engagement rate (reactions + comments per 100 views) - using 90d data
            engagement = ((article['reactions_90d'] + article['comments_90d']) / views) * 100
            
            # Quality score: weighted average of completion and engagement
            # Completion matters more for quality (70%), engagement adds value (30%)
            quality_score = (completion * 0.7) + (min(engagement, 20) * 1.5)
            
            scored_articles.append({
                'title': article['title'],
                'age_days': int(article['age_days']) if article['age_days'] else 0,
                'quality_score': quality_score,
                'completion': completion,
                'engagement': engagement
            })
        
        # Sort by quality score
        scored_articles.sort(key=lambda x: x['quality_score'], reverse=True)
        
        print(f"\n\n⭐ QUALITY SCORES (Completion + Engagement)")
        print("-" * 100)
        print(f"{'Title':<50} {'Quality':>9} {'Read %':>8} {'Engage %':>10}")
        print("-" * 100)
        
        for article in scored_articles[:10]:
            title = article['title'][:47] + "..." if len(article['title']) > 50 else article['title']
            
            print(f"{title:<50} {article['quality_score']:>8.1f} "
                  f"{article['completion']:>7.1f}% {article['engagement']:>9.1f}%")
        
        print("\n💡 Quality Score = (Read Completion × 70%) + (Engagement Rate × 30%)")
        print("   High quality = People read it fully AND engage with it")
        print("   ⚠️ Scores based on last 90 days of data (consistent period for all metrics)")
    
    def analyze_article_daily(self, article_id: int):
        """Show daily breakdown for a specific article"""
        cursor = self.conn.cursor()
        
        # Get article info
        cursor.execute("""
            SELECT DISTINCT title, published_at, reading_time_minutes
            FROM article_metrics
            WHERE article_id = ?
        """, (article_id,))
        
        article_info = cursor.fetchone()
        if not article_info:
            print(f"❌ Article {article_id} not found")
            return
        
        print(f"\n📊 DAILY BREAKDOWN: {article_info['title']}")
        print("-" * 100)
        print(f"Published: {article_info['published_at'][:10] if article_info['published_at'] else 'N/A'}")
        print(f"Length: {article_info['reading_time_minutes']} minutes")
        print()
        
        # Get daily data
        cursor.execute("""
            SELECT 
                date,
                page_views,
                average_read_time_seconds,
                reactions_like,
                reactions_unicorn,
                reactions_readinglist,
                reactions_total,
                comments_total
            FROM daily_analytics
            WHERE article_id = ?
            AND page_views > 0
            ORDER BY date DESC
            LIMIT 30
        """, (article_id,))
        
        days = cursor.fetchall()
        
        print(f"{'Date':<12} {'Views':>7} {'Read(s)':>9} {'Likes':>7} {'🦄':>5} {'📖':>5} {'💬':>5}")
        print("-" * 100)
        
        for day in days:
            print(f"{day['date']:<12} {day['page_views']:>7} "
                  f"{day['average_read_time_seconds']:>9} "
                  f"{day['reactions_like']:>7} "
                  f"{day['reactions_unicorn']:>5} "
                  f"{day['reactions_readinglist']:>5} "
                  f"{day['comments_total']:>5}")

def main():
    parser = argparse.ArgumentParser(description="Quality Analytics Dashboard")
    parser.add_argument('--db', default='devto_metrics.db', help='Database path')
    parser.add_argument('--full', action='store_true', help='Show full dashboard')
    parser.add_argument('--read-time', action='store_true', help='Show read time analysis')
    parser.add_argument('--reactions', action='store_true', help='Show reaction breakdown')
    parser.add_argument('--long-tail', action='store_true', help='Show long-tail champions')
    parser.add_argument('--quality', action='store_true', help='Show quality scores')
    parser.add_argument('--article', type=int, metavar='ID', help='Daily breakdown for article')
    
    args = parser.parse_args()
    
    analytics = QualityAnalytics(args.db)
    
    # If no specific analysis requested, show full dashboard
    if not any([args.read_time, args.reactions, args.long_tail, args.quality, args.article]):
        args.full = True
    
    if args.full:
        analytics.show_quality_dashboard()
    else:
        analytics.connect()
        if args.read_time:
            analytics.show_read_time_analysis()
        if args.reactions:
            analytics.show_reaction_breakdown()
        if args.long_tail:
            analytics.show_long_tail_champions()
        if args.quality:
            analytics.show_quality_scores()
    
    if args.article:
        analytics.analyze_article_daily(args.article)

if __name__ == "__main__":
    main()
