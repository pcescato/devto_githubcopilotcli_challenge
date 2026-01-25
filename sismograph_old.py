#!/usr/bin/env python3
"""
Advanced Analytics - Combining all historical data
Analyses croisées et insights avancés
"""

import argparse
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
from core.database import DatabaseManager

class AdvancedAnalytics:
    def __init__(self, db_path: str):
        self.db = DatabaseManager(db_path)
    
    def article_follower_correlation(self):
        """
        Corrélation: Quel article a apporté le plus de followers ?
        Analyse les pics de followers après publication
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        print("\n📊 ARTICLE → FOLLOWER CORRELATION")
        print("=" * 100)
        
        # Get all follower events with new followers
        cursor.execute("""
            SELECT collected_at, follower_count, new_followers_since_last
            FROM follower_events
            WHERE new_followers_since_last > 0
            ORDER BY collected_at
        """)
        
        follower_events = cursor.fetchall()
        
        # Get all articles with publication date
        cursor.execute("""
            SELECT 
                article_id,
                title,
                published_at,
                MAX(views) as total_views,
                MAX(reactions) as total_reactions,
                MAX(comments) as total_comments
            FROM article_metrics
            WHERE published_at IS NOT NULL
            GROUP BY article_id
            ORDER BY published_at DESC
        """)
        
        articles = cursor.fetchall()
        
        # Correlate: for each follower spike, find the article published around that time
        article_impact = []
        
        for article in articles:
            pub_date = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))
            
            # Look for follower spikes in the 7 days after publication
            followers_gained = 0
            
            for event in follower_events:
                event_date = datetime.fromisoformat(event['collected_at'].replace('Z', '+00:00'))
                days_diff = (event_date - pub_date).days
                
                if 0 <= days_diff <= 7:  # Within 7 days after publication
                    followers_gained += event['new_followers_since_last']
            
            if followers_gained > 0:
                article_impact.append({
                    'title': article['title'],
                    'published': pub_date.strftime('%Y-%m-%d'),
                    'followers': followers_gained,
                    'views': article['total_views'],
                    'reactions': article['total_reactions'],
                    'comments': article['total_comments']
                })
        
        # Sort by followers gained
        article_impact.sort(key=lambda x: x['followers'], reverse=True)
        
        print(f"\n{'Article':<45} {'Date':<12} {'New Followers':<15} {'Views':<8} {'Reactions'}")
        print("-" * 100)
        
        for impact in article_impact[:15]:
            title = impact['title'][:42] + "..." if len(impact['title']) > 45 else impact['title']
            print(f"{title:<45} {impact['published']:<12} {impact['followers']:<15} "
                  f"{impact['views']:<8} {impact['reactions']}")
        
        # Summary statistics
        if article_impact:
            total_followers = sum(a['followers'] for a in article_impact)
            avg_followers = statistics.mean(a['followers'] for a in article_impact)
            print(f"\n📈 Total new followers tracked: {total_followers}")
            print(f"📈 Average per article: {avg_followers:.1f}")
        
        conn.close()
    
    def engagement_evolution(self, article_id: int):
        """
        Évolution détaillée de l'engagement pour un article
        Montre la courbe de croissance avec tous les indicateurs
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Get article info
        cursor.execute("""
            SELECT title, published_at
            FROM article_metrics
            WHERE article_id = ?
            LIMIT 1
        """, (article_id,))
        
        article = cursor.fetchone()
        if not article:
            print(f"❌ Article {article_id} not found")
            conn.close()
            return
        
        print(f"\n📈 ENGAGEMENT EVOLUTION")
        print("=" * 100)
        print(f"Article: {article['title']}")
        print(f"Published: {article['published_at']}")
        print("=" * 100)
        
        # Get all metrics over time
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
        
        metrics = cursor.fetchall()
        
        if len(metrics) < 2:
            print("\n⚠️  Not enough data points yet (need at least 2 collections)")
            conn.close()
            return
        
        print(f"\n{'Time':<20} {'Views':<10} {'Δ Views':<12} {'Reactions':<12} {'Comments':<10} {'Engagement %'}")
        print("-" * 100)
        
        prev_views = 0
        for metric in metrics:
            delta_views = metric['views'] - prev_views
            engagement_rate = ((metric['reactions'] + metric['comments']) / metric['views'] * 100) if metric['views'] > 0 else 0
            
            timestamp = datetime.fromisoformat(metric['collected_at'].replace('Z', '+00:00'))
            
            print(f"{timestamp.strftime('%Y-%m-%d %H:%M'):<20} {metric['views']:<10} "
                  f"{delta_views:+<12} {metric['reactions']:<12} {metric['comments']:<10} {engagement_rate:.2f}%")
            
            prev_views = metric['views']
        
        # Calculate velocity statistics
        time_diffs = []
        view_diffs = []
        
        for i in range(1, len(metrics)):
            t1 = datetime.fromisoformat(metrics[i-1]['collected_at'].replace('Z', '+00:00'))
            t2 = datetime.fromisoformat(metrics[i]['collected_at'].replace('Z', '+00:00'))
            hours_diff = (t2 - t1).total_seconds() / 3600
            
            if hours_diff > 0:
                time_diffs.append(hours_diff)
                views_diff = metrics[i]['views'] - metrics[i-1]['views']
                views_per_hour = views_diff / hours_diff
                view_diffs.append(views_per_hour)
        
        if view_diffs:
            print(f"\n📊 VELOCITY STATS")
            print("-" * 100)
            print(f"Peak velocity: {max(view_diffs):.1f} views/hour")
            print(f"Average velocity: {statistics.mean(view_diffs):.1f} views/hour")
            print(f"Current velocity: {view_diffs[-1]:.1f} views/hour")
        
        conn.close()
    
    def best_publishing_times(self):
        """
        Analyse: Quels jours/heures fonctionnent le mieux ?
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        print(f"\n⏰ BEST PUBLISHING TIMES")
        print("=" * 80)
        
        cursor.execute("""
            SELECT 
                article_id,
                title,
                published_at,
                MAX(views) as total_views,
                MAX(reactions) as total_reactions,
                MAX(comments) as total_comments
            FROM article_metrics
            WHERE published_at IS NOT NULL
            GROUP BY article_id
        """)
        
        articles = cursor.fetchall()
        
        # Group by day of week
        day_stats = defaultdict(lambda: {'views': [], 'reactions': [], 'comments': []})
        hour_stats = defaultdict(lambda: {'views': [], 'reactions': [], 'comments': []})
        
        for article in articles:
            pub_date = datetime.fromisoformat(article['published_at'].replace('Z', '+00:00'))
            day_name = pub_date.strftime('%A')
            hour = pub_date.hour
            
            day_stats[day_name]['views'].append(article['total_views'])
            day_stats[day_name]['reactions'].append(article['total_reactions'])
            day_stats[day_name]['comments'].append(article['total_comments'])
            
            hour_stats[hour]['views'].append(article['total_views'])
            hour_stats[hour]['reactions'].append(article['total_reactions'])
            hour_stats[hour]['comments'].append(article['total_comments'])
        
        # Calculate averages
        print(f"\n📅 BY DAY OF WEEK")
        print("-" * 80)
        print(f"{'Day':<12} {'Articles':<10} {'Avg Views':<12} {'Avg Reactions':<15} {'Avg Comments'}")
        print("-" * 80)
        
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for day in days_order:
            if day in day_stats:
                stats = day_stats[day]
                count = len(stats['views'])
                avg_views = statistics.mean(stats['views'])
                avg_reactions = statistics.mean(stats['reactions'])
                avg_comments = statistics.mean(stats['comments'])
                
                print(f"{day:<12} {count:<10} {avg_views:<12.0f} {avg_reactions:<15.1f} {avg_comments:.1f}")
        
        # Hour analysis (simplified - only show hours with data)
        print(f"\n🕐 BY HOUR OF DAY (UTC)")
        print("-" * 80)
        print(f"{'Hour':<8} {'Articles':<10} {'Avg Views':<12} {'Avg Reactions'}")
        print("-" * 80)
        
        for hour in sorted(hour_stats.keys()):
            stats = hour_stats[hour]
            count = len(stats['views'])
            avg_views = statistics.mean(stats['views'])
            avg_reactions = statistics.mean(stats['reactions'])
            
            print(f"{hour:02d}:00 {count:<10} {avg_views:<12.0f} {avg_reactions:.1f}")
        
        conn.close()
    
    def comment_engagement_correlation(self):
        """
        Corrélation: Articles avec beaucoup de commentaires = plus de followers ?
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        print(f"\n💬 COMMENT ↔ FOLLOWER CORRELATION")
        print("=" * 80)
        
        cursor.execute("""
            SELECT 
                am.article_id,
                am.title,
                am.published_at,
                MAX(am.views) as views,
                MAX(am.reactions) as reactions,
                MAX(am.comments) as comments,
                COUNT(DISTINCT c.comment_id) as comment_count,
                COUNT(DISTINCT c.author_username) as unique_commenters
            FROM article_metrics am
            LEFT JOIN comments c ON am.article_id = c.article_id
            WHERE am.published_at IS NOT NULL
            GROUP BY am.article_id
            ORDER BY comments DESC
            LIMIT 20
        """)
        
        articles = cursor.fetchall()
        
        print(f"\n{'Article':<40} {'Comments':<10} {'Unique':<8} {'Views':<10} {'Engagement %'}")
        print("-" * 80)
        
        for article in articles:
            title = article['title'][:37] + "..." if len(article['title']) > 40 else article['title']
            engagement = ((article['reactions'] + article['comments']) / article['views'] * 100) if article['views'] > 0 else 0
            
            print(f"{title:<40} {article['comments']:<10} {article['unique_commenters']:<8} "
                  f"{article['views']:<10} {engagement:.2f}%")
        
        conn.close()
    
    def full_report(self):
        """Generate comprehensive analytics report"""
        print("\n" + "=" * 100)
        print(" " * 35 + "📊 FULL ANALYTICS REPORT")
        print("=" * 100)
        
        self.article_follower_correlation()
        self.best_publishing_times()
        self.comment_engagement_correlation()


    def milestone_timeline(self, article_id: int = None):
        """
        Affiche une timeline des événements marquants
        (changements de titre, curation staff, suppressions, etc.)
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        print(f"\n📅 MILESTONE TIMELINE")
        print("=" * 100)
        
        # Récupérer les événements
        if article_id:
            query = """
                SELECT 
                    id,
                    article_id,
                    event_type,
                    description,
                    occurred_at
                FROM milestone_events
                WHERE article_id = ?
                ORDER BY occurred_at DESC
            """
            cursor.execute(query, (article_id,))
        else:
            query = """
                SELECT 
                    id,
                    article_id,
                    event_type,
                    description,
                    occurred_at
                FROM milestone_events
                ORDER BY occurred_at DESC
            """
            cursor.execute(query)
        
        events = cursor.fetchall()
        
        if not events:
            print("\n⚪ Aucun événement milestone enregistré")
            if not article_id:
                print("   Conseil : Les événements sont enregistrés via db.log_milestone()")
            conn.close()
            return
        
        # Afficher les événements
        print(f"\n{'Date':<20} {'Type':<15} {'Article ID':<12} {'Description':<45}")
        print("-" * 100)
        
        for event in events:
            occurred = event['occurred_at'][:19] if event['occurred_at'] else 'N/A'
            event_type = event['event_type'][:14] if event['event_type'] else 'Unknown'
            art_id = str(event['article_id']) if event['article_id'] else 'N/A'
            description = event['description'][:42] + "..." if len(event['description']) > 45 else event['description']
            
            print(f"{occurred:<20} {event_type:<15} {art_id:<12} {description:<45}")
        
        # Statistiques
        print(f"\n📊 STATISTIQUES")
        print("-" * 100)
        
        # Compter par type
        cursor.execute("""
            SELECT 
                event_type,
                COUNT(*) as count
            FROM milestone_events
            GROUP BY event_type
            ORDER BY count DESC
        """)
        
        types = cursor.fetchall()
        print(f"{'Type d\'événement':<30} {'Nombre':<10}")
        print("-" * 40)
        
        for event_type in types:
            print(f"{event_type['event_type']:<30} {event_type['count']:<10}")
        
        total = len(events)
        print(f"\n📌 Total d'événements : {total}")
        
        # Articles affectés
        cursor.execute("""
            SELECT COUNT(DISTINCT article_id) as count
            FROM milestone_events
            WHERE article_id IS NOT NULL
        """)
        
        result = cursor.fetchone()
        articles_affected = result['count'] if result['count'] else 0
        print(f"📄 Articles affectés : {articles_affected}")
        
        # Récemment (derniers 7 jours)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM milestone_events
            WHERE occurred_at >= datetime('now', '-7 days')
        """)
        
        result = cursor.fetchone()
        recent = result['count'] if result['count'] else 0
        print(f"🔥 Événements cette semaine : {recent}")
        
        conn.close()

def main():
    parser = argparse.ArgumentParser(
        description='Advanced Analytics - Combining all historical data'
    )
    
    parser.add_argument('--db', default='devto_metrics.db', help='Database file path')
    parser.add_argument('--follower-correlation', action='store_true',
                       help='Analyze which articles brought followers')
    parser.add_argument('--evolution', type=int, metavar='ARTICLE_ID',
                       help='Detailed evolution of specific article')
    parser.add_argument('--best-times', action='store_true',
                       help='Analyze best publishing times')
    parser.add_argument('--comment-correlation', action='store_true',
                       help='Correlation between comments and engagement')
    parser.add_argument('--full-report', action='store_true',
                       help='Generate full analytics report')
    parser.add_argument('--milestones', action='store_true',
                       help='Show milestone timeline')
    parser.add_argument('--milestone-article', type=int, metavar='ARTICLE_ID',
                       help='Show milestones for specific article')
    
    args = parser.parse_args()
    
    analytics = AdvancedAnalytics(args.db)
    
    if args.full_report:
        analytics.full_report()
    else:
        if args.follower_correlation:
            analytics.article_follower_correlation()
        if args.evolution:
            analytics.engagement_evolution(args.evolution)
        if args.best_times:
            analytics.best_publishing_times()
        if args.comment_correlation:
            analytics.comment_engagement_correlation()
        if args.milestones or args.milestone_article:
            analytics.milestone_timeline(args.milestone_article)


if __name__ == "__main__":
    main()