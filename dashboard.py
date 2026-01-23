#!/usr/bin/env python3
"""
DEV.to Personal Dashboard
Un dashboard complet pour comprendre votre impact réel
"""

from datetime import datetime, timedelta
from collections import Counter, defaultdict
import argparse
import re
from core.database import DatabaseManager
from core.topic_intelligence import TopicIntelligence

class DevToDashboard:
    def __init__(self, db_path: str = "devto_metrics.db"):
        self.db = DatabaseManager(db_path)
        self.db_path = db_path
    
    def show_full_dashboard(self):
        """Display full dashboard"""
        
        print("\n" + "="*100)
        print("📊 DEV.TO PERSONAL DASHBOARD")
        print("="*100)
        
        # 1. Latest article details
        self.show_latest_article_detail()
        
        # 2. Last 5 articles
        self.show_last_5_articles()
        
        # 3. Global trend
        self.show_global_trend()
        
        # 4. Significant insights
        self.show_significant_insights()
        
        # 5. Top commenters with quality and sentiment
        self.show_top_commenters()
        
        # 6. Performance comparison
        self.show_article_comparison()

        # 7. Author DNA analysis
        self.display_author_dna()
        
        print("\n" + "="*100)

    def display_author_dna(self):
        analyzer = TopicIntelligence(self.db_path)
        print("\n" + "🧬" + " --- VOTRE PROFIL D'AUTEUR (DNA) ---")
        analyzer.analyze_dna()
    
    def show_latest_article_detail(self):
        """Detailed metrics for latest article"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Latest published article
        cursor.execute("""
            SELECT 
                article_id,
                title,
                MAX(collected_at) as last_check,
                MAX(views) as views,
                MAX(reactions) as reactions,
                MAX(comments) as comments,
                published_at
            FROM article_metrics
            GROUP BY article_id
            ORDER BY published_at DESC
            LIMIT 1
        """)
        
        article = cursor.fetchone()
        if not article:
            print("\n❌ No articles found")
            conn.close()
            return
        
        article_id = article['article_id']
        
        print(f"\n📝 LATEST ARTICLE: {article['title']}")
        print("-" * 100)
        print(f"Article ID: {article_id}")
        
        # Format dates safely
        pub_date = article['published_at'][:10] if article['published_at'] else 'N/A'
        last_check = article['last_check'][:16] if article['last_check'] else 'N/A'
        
        print(f"Published: {pub_date}")
        print(f"Last updated: {last_check}")
        print()
        
        # Current metrics
        print(f"📊 Current metrics:")
        print(f"  Views:     {article['views']:>6}")
        print(f"  Reactions: {article['reactions']:>6}")
        print(f"  Comments:  {article['comments']:>6}")
        
        # Engagement rate
        if article['views'] > 0:
            reaction_rate = (article['reactions'] / article['views']) * 100
            comment_rate = (article['comments'] / article['views']) * 100
            print(f"\n💡 Engagement rate:")
            print(f"  Reaction rate: {reaction_rate:.2f}%")
            print(f"  Comment rate:  {comment_rate:.2f}%")
        
        # Evolution over time
        cursor.execute("""
            SELECT 
                collected_at,
                views,
                reactions,
                comments
            FROM article_metrics
            WHERE article_id = ?
            ORDER BY collected_at
        """, (article_id,))
        
        snapshots = cursor.fetchall()
        if len(snapshots) > 1:
            first = snapshots[0]
            last = snapshots[-1]
            
            # Parse datetime strings (ISO format with T or space separator)
            def parse_iso(date_str):
                if not date_str:
                    return None
                # Remove Z suffix and replace T with space
                clean_str = date_str.replace('Z', '').replace('T', ' ')
                # Try parsing
                try:
                    return datetime.fromisoformat(clean_str)
                except:
                    # Fallback for other formats
                    return datetime.strptime(clean_str[:19], '%Y-%m-%d %H:%M:%S')
            
            first_time = parse_iso(first['collected_at'])
            last_time = parse_iso(last['collected_at'])
            
            if first_time and last_time:
                duration = last_time - first_time
                hours = duration.total_seconds() / 3600

                total_hours = duration.total_seconds() / 3600
                if total_hours < 24:
                    h = int(total_hours)
                    m = int((total_hours - h) * 60)
                    duration_str = f"{h}h{m:02d}min"
                else:
                    duration_str = f"{duration.days}d {int(duration.seconds/3600)}h"
                
                if hours > 0:
                    views_growth = last['views'] - first['views']
                    views_per_hour = views_growth / hours
                    
                    print(f"Growth (over {duration_str}):")
                    print(f"  +{views_growth} views ({views_per_hour:.1f} views/hour)")
                    print(f"  +{last['reactions'] - first['reactions']} reactions")
                    print(f"  +{last['comments'] - first['comments']} comments")
        
        # Recent comments
        cursor.execute("""
            SELECT 
                author_name,
                body_length,
                created_at
            FROM comments
            WHERE article_id = ?
            ORDER BY created_at DESC
            LIMIT 3
        """, (article_id,))
        
        recent_comments = cursor.fetchall()
        if recent_comments:
            print(f"\n💬 Recent comments:")
            for comment in recent_comments:
                created = comment['created_at'][:10] if comment['created_at'] else 'N/A'
                print(f"  • {comment['author_name']} ({comment['body_length']} chars) - {created}")
        
    
    def show_last_5_articles(self):
        """View of last 5 articles"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                article_id,
                title,
                published_at,
                MAX(views) as views,
                MAX(reactions) as reactions,
                MAX(comments) as comments
            FROM article_metrics
            GROUP BY article_id
            ORDER BY published_at DESC
            LIMIT 5
        """)
        
        articles = cursor.fetchall()
        
        print(f"\n\n📚 LAST 5 ARTICLES")
        print("-" * 100)
        print(f"{'Title':<50} {'Published':<12} {'Views':>7} {'Reacts':>7} {'Cmnts':>6} {'Eng%':>6}")
        print("-" * 100)
        
        for article in articles:
            title = article['title'][:47] + "..." if len(article['title']) > 50 else article['title']
            pub_date = article['published_at'][:10] if article['published_at'] else 'N/A'
            
            engagement = 0
            if article['views'] > 0:
                engagement = ((article['reactions'] + article['comments']) / article['views']) * 100
            
            print(f"{title:<50} {pub_date:<12} {article['views']:>7} {article['reactions']:>7} "
                  f"{article['comments']:>6} {engagement:>5.1f}%")
        
        conn.close()
    
    def show_global_trend(self):
        """Global trend"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Get max metrics per article for last 30 days
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT article_id) as articles,
                SUM(max_views) as total_views,
                SUM(max_reactions) as total_reactions,
                SUM(max_comments) as total_comments
            FROM (
                SELECT 
                    article_id,
                    MAX(views) as max_views,
                    MAX(reactions) as max_reactions,
                    MAX(comments) as max_comments
                FROM article_metrics
                WHERE collected_at >= datetime('now', '-30 days')
                GROUP BY article_id
            )
        """)
        
        recent = cursor.fetchone()
        
        # Get max metrics per article for previous 30 days
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT article_id) as articles,
                SUM(max_views) as total_views,
                SUM(max_reactions) as total_reactions,
                SUM(max_comments) as total_comments
            FROM (
                SELECT 
                    article_id,
                    MAX(views) as max_views,
                    MAX(reactions) as max_reactions,
                    MAX(comments) as max_comments
                FROM article_metrics
                WHERE collected_at >= datetime('now', '-60 days')
                AND collected_at < datetime('now', '-30 days')
                GROUP BY article_id
            )
        """)
        
        previous = cursor.fetchone()
        
        print(f"\n\n📈 GLOBAL TREND (Last 30 days)")
        print("-" * 100)
        
        if recent:
            print(f"Active articles:   {recent['articles']}")
            print(f"Total views:       {recent['total_views']:,}")
            print(f"Total reactions:   {recent['total_reactions']:,}")
            print(f"Total comments:    {recent['total_comments']:,}")
            
            if previous and previous['total_views'] and previous['total_views'] > 0:
                views_change = ((recent['total_views'] - previous['total_views']) / previous['total_views']) * 100
                
                arrow = "↗" if views_change > 0 else "↘"
                print(f"\nChange vs previous 30 days: {arrow} {views_change:+.1f}%")
        
        # Average per article (all time)
        cursor.execute("""
            SELECT 
                AVG(max_views) as avg_views,
                AVG(max_reactions) as avg_reactions,
                AVG(max_comments) as avg_comments
            FROM (
                SELECT 
                    article_id,
                    MAX(views) as max_views,
                    MAX(reactions) as max_reactions,
                    MAX(comments) as max_comments
                FROM article_metrics
                GROUP BY article_id
            )
        """)
        
        avg = cursor.fetchone()
        print(f"\n📊 Average per article (all time):")
        print(f"  Views:     {avg['avg_views']:.0f}")
        print(f"  Reactions: {avg['avg_reactions']:.1f}")
        print(f"  Comments:  {avg['avg_comments']:.1f}")
        
        conn.close()
    
    def show_significant_insights(self):
        """Automatic significant insights"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        print(f"\n\n💡 SIGNIFICANT INSIGHTS")
        print("-" * 100)
        
        insights = []
        
        # 1. Article restarting
        cursor.execute("""
            SELECT 
                a1.article_id,
                a1.title,
                a1.views as recent_views,
                a2.views as old_views
            FROM article_metrics a1
            JOIN article_metrics a2 ON a1.article_id = a2.article_id
            WHERE a1.collected_at >= datetime('now', '-7 days')
            AND a2.collected_at <= datetime('now', '-14 days')
            AND a1.views > a2.views * 1.5
            AND a2.views > 50
            GROUP BY a1.article_id
            ORDER BY (a1.views - a2.views) DESC
            LIMIT 1
        """)
        
        restarting = cursor.fetchone()
        if restarting:
            growth = restarting['recent_views'] - restarting['old_views']
            insights.append(f"🚀 '{restarting['title'][:60]}...' is restarting: +{growth} views this week")
        
        # 2. Most engaged reader recently
        cursor.execute("""
            SELECT 
                author_name,
                COUNT(*) as comment_count,
                AVG(body_length) as avg_length
            FROM comments
            WHERE collected_at >= datetime('now', '-30 days')
            AND author_name IS NOT NULL
            GROUP BY author_name
            ORDER BY comment_count DESC
            LIMIT 1
        """)
        
        top_commenter = cursor.fetchone()
        if top_commenter and top_commenter['author_name'] and top_commenter['comment_count'] > 2:
            avg_len = top_commenter['avg_length'] if top_commenter['avg_length'] else 0
            insights.append(f"👤 {top_commenter['author_name']} is very active: "
                          f"{top_commenter['comment_count']} comments this month "
                          f"({avg_len:.0f} chars avg)")
        
        # 3. Best engagement rate recently
        cursor.execute("""
            SELECT 
                title,
                MAX(views) as views,
                MAX(comments) as comments
            FROM article_metrics
            WHERE published_at >= datetime('now', '-60 days')
            AND views > 50
            GROUP BY article_id
            ORDER BY (CAST(comments AS FLOAT) / views) DESC
            LIMIT 1
        """)
        
        best_engagement = cursor.fetchone()
        if best_engagement and best_engagement['views'] > 0:
            rate = (best_engagement['comments'] / best_engagement['views']) * 100
            insights.append(f"💬 Best engagement: '{best_engagement['title'][:60]}...' "
                          f"({rate:.1f}% comment rate)")
        
        # 4. Follower growth
        cursor.execute("""
            SELECT 
                follower_count,
                new_followers_since_last,
                collected_at
            FROM follower_events
            ORDER BY collected_at DESC
            LIMIT 2
        """)
        
        followers = cursor.fetchall()
        if len(followers) == 2:
            if followers[0]['new_followers_since_last'] > 5:
                insights.append(f"👥 +{followers[0]['new_followers_since_last']} new followers recently "
                              f"(total: {followers[0]['follower_count']})")
        
        # Display
        if insights:
            for insight in insights:
                print(f"  • {insight}")
        else:
            print("  • Not enough data to generate insights (collect for a few days)")
        
        conn.close()
    
    def show_top_commenters(self):
        """Analyze commenters with quality and sentiment"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        print(f"\n\n👥 TOP COMMENTERS (Quality & engagement analysis)")
        print("-" * 100)
        
        cursor.execute("""
            SELECT 
                author_name,
                author_username,
                COUNT(*) as comment_count,
                COUNT(DISTINCT article_id) as articles_commented,
                AVG(body_length) as avg_length,
                SUM(body_length) as total_chars,
                MIN(created_at) as first_comment,
                MAX(created_at) as last_comment
            FROM comments
            WHERE author_name IS NOT NULL
            GROUP BY author_username
            HAVING comment_count > 1
            ORDER BY comment_count DESC, avg_length DESC
            LIMIT 10
        """)
        
        commenters = cursor.fetchall()
        
        print(f"{'Name':<25} {'Comments':>8} {'Articles':>8} {'Avg Length':>11} {'Quality':>8} {'Sentiment':>10}")
        print("-" * 100)
        
        for commenter in commenters:
            # Handle None avg_length
            avg_len = commenter['avg_length'] if commenter['avg_length'] else 0
            
            # Quality score based on length and diversity
            quality_score = min(10, (avg_len / 100) * (commenter['articles_commented']))
            
            # Basic sentiment analysis (based on length and engagement)
            if avg_len > 500:
                sentiment = "🔥 Passionate"
            elif avg_len > 300:
                sentiment = "💬 Engaged"
            elif avg_len > 100:
                sentiment = "👍 Interested"
            else:
                sentiment = "✓ Basic"
            
            name = commenter['author_name'][:22] + "..." if len(commenter['author_name']) > 25 else commenter['author_name']
            
            print(f"{name:<25} {commenter['comment_count']:>8} {commenter['articles_commented']:>8} "
                  f"{avg_len:>9.0f}ch {quality_score:>7.1f}/10 {sentiment:>10}")
        
        # Most loyal commenters (return often)
        cursor.execute("""
            SELECT 
                author_username,
                COUNT(DISTINCT article_id) as articles
            FROM comments
            GROUP BY author_username
            HAVING articles >= 3
            ORDER BY articles DESC
            LIMIT 3
        """)
        
        loyal = cursor.fetchall()
        if loyal:
            print(f"\n⭐ Most loyal readers (comment on multiple articles):")
            for reader in loyal:
                print(f"  • {reader['author_username']} commented on {reader['articles']} different articles")
        
        conn.close()
    
    def show_article_comparison(self):
        """Performance comparison between articles"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        print(f"\n\n📊 PERFORMANCE COMPARISON")
        print("-" * 100)
        
        cursor.execute("""
            SELECT 
                article_id,
                title,
                published_at,
                MAX(views) as views,
                MAX(reactions) as reactions,
                MAX(comments) as comments,
                reading_time_minutes
            FROM article_metrics
            WHERE published_at IS NOT NULL
            GROUP BY article_id
            ORDER BY views DESC
        """)
        
        articles = cursor.fetchall()
        
        # Calculate comparative metrics
        article_data = []
        for article in articles:
            engagement_rate = 0
            if article['views'] > 0:
                engagement_rate = ((article['reactions'] + article['comments']) / article['views']) * 100
            
            # Average comment length
            cursor.execute("""
                SELECT AVG(body_length) as avg_comment_length
                FROM comments
                WHERE article_id = ?
            """, (article['article_id'],))
            
            comment_data = cursor.fetchone()
            avg_comment_length = comment_data['avg_comment_length'] if comment_data else 0
            if avg_comment_length is None:
                avg_comment_length = 0
            
            article_data.append({
                'title': article['title'],
                'views': article['views'],
                'reactions': article['reactions'],
                'comments': article['comments'],
                'engagement_rate': engagement_rate,
                'reading_time': article['reading_time_minutes'],
                'avg_comment_length': avg_comment_length
            })
        
        # Top 5 by views
        print("\n🏆 Top 5 by views:")
        for i, article in enumerate(article_data[:5], 1):
            title = article['title'][:60] + "..." if len(article['title']) > 60 else article['title']
            print(f"  {i}. {title}")
            print(f"     {article['views']} views | {article['reactions']} reactions | "
                  f"{article['comments']} comments | {article['engagement_rate']:.1f}% engagement")
        
        # Top 5 by engagement
        sorted_by_engagement = sorted(article_data, key=lambda x: x['engagement_rate'], reverse=True)
        print("\n💬 Top 5 by engagement rate:")
        for i, article in enumerate(sorted_by_engagement[:5], 1):
            title = article['title'][:60] + "..." if len(article['title']) > 60 else article['title']
            print(f"  {i}. {title}")
            print(f"     {article['engagement_rate']:.2f}% engagement | {article['views']} views | "
                  f"{article['avg_comment_length']:.0f} chars/comment")
        
        # Analysis by article length
        if any(a['reading_time'] for a in article_data):
            print("\n📖 Performance by article length:")
            
            short = [a for a in article_data if a['reading_time'] and a['reading_time'] < 5]
            medium = [a for a in article_data if a['reading_time'] and 5 <= a['reading_time'] < 10]
            long = [a for a in article_data if a['reading_time'] and a['reading_time'] >= 10]
            
            for articles_list, label, description in [
                (short, "short", "Short (<5 min)"),
                (medium, "medium", "Medium (5-10 min)"),
                (long, "long", "Long (>10 min)")
            ]:
                if articles_list:
                    avg_views = sum(a['views'] for a in articles_list) / len(articles_list)
                    avg_engagement = sum(a['engagement_rate'] for a in articles_list) / len(articles_list)
                    print(f"  • {description}: {len(articles_list)} articles | "
                          f"Avg {avg_views:.0f} views | {avg_engagement:.1f}% engagement")
        
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="DEV.to Personal Dashboard")
    parser.add_argument('--db', default='devto_metrics.db', help='Path to database')
    
    args = parser.parse_args()
    
    dashboard = DevToDashboard(args.db)
    dashboard.show_full_dashboard()

if __name__ == "__main__":
    main()