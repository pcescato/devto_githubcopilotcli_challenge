#!/usr/bin/env python3
"""
Comment Analysis Tool - Deep dive into article engagement
Analyse qualitative de l'engagement via les commentaires
"""

import sqlite3
import argparse
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple
import re

class CommentAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def analyze_article_comments(self, article_id: int):
        """Deep analysis of comments for a specific article"""
        cursor = self.conn.cursor()
        
        # Get article info
        cursor.execute("""
            SELECT DISTINCT article_title, collected_at
            FROM comments
            WHERE article_id = ?
            ORDER BY collected_at DESC
            LIMIT 1
        """, (article_id,))
        
        article = cursor.fetchone()
        if not article:
            print(f"❌ No comments found for article {article_id}")
            return
        
        print(f"\n💬 COMMENT ANALYSIS")
        print("=" * 80)
        print(f"Article: {article['article_title']}")
        print(f"Last updated: {article['collected_at']}")
        print("=" * 80)
        
        # Get all comments
        cursor.execute("""
            SELECT *
            FROM comments
            WHERE article_id = ?
            ORDER BY created_at
        """, (article_id,))
        
        comments = cursor.fetchall()
        
        if not comments:
            print("\n No comments yet")
            return
        
        # Basic stats
        total_comments = len(comments)
        unique_authors = len(set(c['author_username'] for c in comments))
        avg_length = sum(c['body_length'] for c in comments) / total_comments
        
        print(f"\n📊 OVERVIEW")
        print("-" * 80)
        print(f"Total comments: {total_comments}")
        print(f"Unique commenters: {unique_authors}")
        print(f"Average length: {avg_length:.0f} characters")
        print(f"Comments per person: {total_comments/unique_authors:.1f}")
        
        # Timeline
        first_comment = datetime.fromisoformat(comments[0]['created_at'].replace('Z', '+00:00'))
        last_comment = datetime.fromisoformat(comments[-1]['created_at'].replace('Z', '+00:00'))
        duration = last_comment - first_comment
        
        print(f"\n⏱️  TIMELINE")
        print("-" * 80)
        print(f"First comment: {first_comment.strftime('%Y-%m-%d %H:%M')}")
        print(f"Last comment: {last_comment.strftime('%Y-%m-%d %H:%M')}")
        print(f"Duration: {duration.days} days, {duration.seconds // 3600} hours")
        
        # Top commenters
        author_counts = Counter(c['author_username'] for c in comments)
        print(f"\n👥 TOP COMMENTERS")
        print("-" * 80)
        for author, count in author_counts.most_common(5):
            author_name = next((c['author_name'] for c in comments if c['author_username'] == author), author)
            print(f"{author_name} (@{author}): {count} comment{'s' if count > 1 else ''}")
        
        # Comment velocity (comments per day)
        if duration.days > 0:
            comments_per_day = total_comments / duration.days
            print(f"\n📈 VELOCITY")
            print("-" * 80)
            print(f"Comments per day: {comments_per_day:.1f}")
        
        # Engagement depth
        long_comments = sum(1 for c in comments if c['body_length'] > 200)
        short_comments = sum(1 for c in comments if c['body_length'] < 50)
        
        print(f"\n🎯 ENGAGEMENT DEPTH")
        print("-" * 80)
        print(f"Long comments (>200 chars): {long_comments} ({long_comments/total_comments*100:.1f}%)")
        print(f"Short comments (<50 chars): {short_comments} ({short_comments/total_comments*100:.1f}%)")
        
        # Recent activity
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM comments
            WHERE article_id = ?
            AND created_at >= datetime('now', '-7 days')
        """, (article_id,))
        recent = cursor.fetchone()
        
        print(f"\n🔥 RECENT ACTIVITY")
        print("-" * 80)
        print(f"Comments in last 7 days: {recent['count']}")
    
    def compare_article_engagement(self, limit: int = 10):
        """Compare comment engagement across articles"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                article_id,
                article_title,
                COUNT(DISTINCT comment_id) as comment_count,
                COUNT(DISTINCT author_username) as unique_commenters,
                AVG(body_length) as avg_length,
                MIN(created_at) as first_comment,
                MAX(created_at) as last_comment
            FROM comments
            GROUP BY article_id
            ORDER BY comment_count DESC
            LIMIT ?
        """, (limit,))
        
        articles = cursor.fetchall()
        
        print(f"\n📊 ARTICLE ENGAGEMENT COMPARISON")
        print("=" * 100)
        print(f"{'Article':<50} {'Comments':<10} {'Unique':<8} {'Avg Length':<12} {'Duration'}")
        print("-" * 100)
        
        for article in articles:
            title = article['article_title'][:47] + "..." if len(article['article_title']) > 50 else article['article_title']
            
            first = datetime.fromisoformat(article['first_comment'].replace('Z', '+00:00'))
            last = datetime.fromisoformat(article['last_comment'].replace('Z', '+00:00'))
            duration = last - first
            duration_str = f"{duration.days}d {duration.seconds//3600}h"
            
            avg_len = article['avg_length'] if article['avg_length'] else 0
            print(f"{title:<50} {article['comment_count']:<10} {article['unique_commenters']:<8} "
                  f"{avg_len:<12.0f} {duration_str}")
    
    def find_engaged_readers(self):
        """Find your most engaged readers (across all articles)"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                author_username,
                author_name,
                COUNT(DISTINCT article_id) as articles_commented,
                COUNT(*) as total_comments,
                AVG(body_length) as avg_length,
                MIN(created_at) as first_interaction,
                MAX(created_at) as last_interaction
            FROM comments
            GROUP BY author_username
            HAVING total_comments > 1
            ORDER BY total_comments DESC
            LIMIT 20
        """)
        
        readers = cursor.fetchall()
        
        print(f"\n🌟 YOUR MOST ENGAGED READERS")
        print("=" * 100)
        print(f"{'Reader':<30} {'Articles':<10} {'Comments':<10} {'Avg Length':<12} {'Active Period'}")
        print("-" * 100)
        
        for reader in readers:
            name = f"{reader['author_name']} (@{reader['author_username']})"[:28]
            
            first = datetime.fromisoformat(reader['first_interaction'].replace('Z', '+00:00'))
            last = datetime.fromisoformat(reader['last_interaction'].replace('Z', '+00:00'))
            period = (last - first).days
            period_str = f"{period} days" if period > 0 else "same day"
            
            avg_len = reader['avg_length'] if reader['avg_length'] else 0
            print(f"{name:<30} {reader['articles_commented']:<10} {reader['total_comments']:<10} "
                  f"{avg_len:<12.0f} {period_str}")
    
    def comment_timing_analysis(self):
        """Analyze when comments typically arrive"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                comments.article_id,
                comments.article_title,
                article_metrics.published_at as article_published,
                comments.created_at as comment_time
            FROM comments
            JOIN article_metrics ON comments.article_id = article_metrics.article_id
            WHERE article_metrics.published_at IS NOT NULL
        """)
        
        comments = cursor.fetchall()
        
        if not comments:
            print("❌ No data available for timing analysis")
            return
        
        # Group by time since publication
        time_buckets = defaultdict(int)
        
        for comment in comments:
            pub = datetime.fromisoformat(comment['article_published'].replace('Z', '+00:00'))
            comm = datetime.fromisoformat(comment['comment_time'].replace('Z', '+00:00'))
            hours_diff = (comm - pub).total_seconds() / 3600
            
            if hours_diff < 24:
                time_buckets['0-24h'] += 1
            elif hours_diff < 72:
                time_buckets['24-72h'] += 1
            elif hours_diff < 168:  # 7 days
                time_buckets['3-7 days'] += 1
            elif hours_diff < 720:  # 30 days
                time_buckets['1-4 weeks'] += 1
            else:
                time_buckets['1+ months'] += 1
        
        print(f"\n⏰ COMMENT TIMING DISTRIBUTION")
        print("=" * 80)
        print(f"When do comments typically arrive after publication?")
        print("-" * 80)
        
        total = sum(time_buckets.values())
        for bucket, count in sorted(time_buckets.items()):
            percentage = count / total * 100
            bar = '█' * int(percentage / 2)
            print(f"{bucket:<15} {count:>4} ({percentage:>5.1f}%) {bar}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Comment Analysis Tool - Deep dive into article engagement'
    )
    
    parser.add_argument('--db', default='devto_metrics.db', help='Database file path')
    parser.add_argument('--article', type=int, metavar='ID', 
                       help='Analyze comments for specific article')
    parser.add_argument('--compare', action='store_true',
                       help='Compare engagement across articles')
    parser.add_argument('--engaged-readers', action='store_true',
                       help='Find your most engaged readers')
    parser.add_argument('--timing', action='store_true',
                       help='Analyze comment timing patterns')
    parser.add_argument('--full-report', action='store_true',
                       help='Generate full comment analysis report')
    
    args = parser.parse_args()
    
    analyzer = CommentAnalyzer(args.db)
    
    if args.full_report:
        analyzer.compare_article_engagement()
        analyzer.find_engaged_readers()
        analyzer.comment_timing_analysis()
    else:
        if args.article:
            analyzer.analyze_article_comments(args.article)
        if args.compare:
            analyzer.compare_article_engagement()
        if args.engaged_readers:
            analyzer.find_engaged_readers()
        if args.timing:
            analyzer.comment_timing_analysis()
    
    analyzer.close()


if __name__ == "__main__":
    main()