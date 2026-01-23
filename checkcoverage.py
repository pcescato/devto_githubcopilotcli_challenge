#!/usr/bin/env python3
"""
Vérifier quelles dates sont réellement disponibles dans daily_analytics
"""

import sqlite3
from datetime import datetime

def check_daily_analytics_coverage(db_path: str = "devto_metrics.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n" + "="*100)
    print("🔍 VÉRIFICATION COUVERTURE DAILY_ANALYTICS")
    print("="*100)
    
    # Article "Actually Agile" - ID 2969205
    article_id = 2969205
    
    # 1. Info de base
    cursor.execute("""
        SELECT 
            article_id,
            title,
            published_at,
            julianday('now') - julianday(published_at) as age_days
        FROM article_metrics
        WHERE article_id = ?
        LIMIT 1
    """, (article_id,))
    
    info = cursor.fetchone()
    print(f"\n📊 Article: {info['title']}")
    print(f"   Publié: {info['published_at']}")
    print(f"   Âge: {int(info['age_days'])} jours")
    
    # 2. Quelles dates sont disponibles ?
    cursor.execute("""
        SELECT 
            date,
            page_views,
            reactions_total,
            reactions_like,
            reactions_unicorn,
            reactions_readinglist,
            collected_at
        FROM daily_analytics
        WHERE article_id = ?
        ORDER BY date
    """, (article_id,))
    
    days = cursor.fetchall()
    
    print(f"\n📅 DATES DISPONIBLES dans daily_analytics : {len(days)} jours")
    print("-" * 100)
    
    if days:
        print(f"   Première date: {days[0]['date']}")
        print(f"   Dernière date: {days[-1]['date']}")
        print(f"   Collecté le:   {days[0]['collected_at']}")
        
        # Calculer l'écart
        pub_date = datetime.fromisoformat(info['published_at'].replace('Z', '+00:00'))
        first_data_date = datetime.fromisoformat(days[0]['date'])
        gap_days = (first_data_date - pub_date).days
        
        print(f"\n⚠️  ÉCART: {gap_days} jours entre publication et première donnée daily")
        print(f"   → Les réactions des {gap_days} premiers jours sont absentes du breakdown")
        
        # Afficher les 10 premières dates
        print(f"\n📋 Détail des {min(10, len(days))} premières dates :")
        print(f"{'Date':<12} {'Views':>7} {'Reactions':>10} {'Likes':>7} {'Unicorn':>8} {'Bookmark':>9}")
        print("-" * 100)
        
        for day in days[:10]:
            print(f"{day['date']:<12} {day['page_views']:>7} {day['reactions_total']:>10} "
                  f"{day['reactions_like']:>7} {day['reactions_unicorn']:>8} {day['reactions_readinglist']:>9}")
        
        # Somme des réactions dans daily_analytics
        total_reactions_daily = sum(d['reactions_total'] for d in days)
        print(f"\n📊 Total réactions dans daily_analytics: {total_reactions_daily}")
    else:
        print("   ❌ AUCUNE donnée !")
    
    # 3. Comparer avec article_metrics
    cursor.execute("""
        SELECT reactions, comments, views
        FROM article_metrics
        WHERE article_id = ?
        ORDER BY collected_at DESC
        LIMIT 1
    """, (article_id,))
    
    latest = cursor.fetchone()
    print(f"\n📊 Données lifetime (article_metrics):")
    print(f"   Reactions: {latest['reactions']}")
    print(f"   Comments:  {latest['comments']}")
    print(f"   Views:     {latest['views']}")
    
    if days:
        missing_reactions = latest['reactions'] - days[-1]['reactions_total']
        print(f"\n❌ Réactions manquantes: {missing_reactions}")
        print(f"   (= Réactions reçues avant le {days[0]['date']})")
    
    # 4. Vérifier tous les articles
    print(f"\n\n" + "="*100)
    print("📊 RÉSUMÉ POUR TOUS LES ARTICLES")
    print("="*100)
    
    cursor.execute("""
        SELECT 
            am.article_id,
            am.title,
            am.published_at,
            julianday('now') - julianday(am.published_at) as age_days,
            MIN(da.date) as first_daily_date,
            MAX(da.date) as last_daily_date,
            COUNT(DISTINCT da.date) as days_count,
            julianday(MIN(da.date)) - julianday(am.published_at) as gap_days,
            MAX(am.reactions) as lifetime_reactions,
            MAX(da.reactions_total) as daily_reactions
        FROM article_metrics am
        LEFT JOIN daily_analytics da ON am.article_id = da.article_id
        WHERE am.published_at IS NOT NULL
        GROUP BY am.article_id
        ORDER BY gap_days DESC
    """)
    
    all_articles = cursor.fetchall()
    
    print(f"\n{'Title':<45} {'Age':>6} {'Gap':>6} {'Days':>6} {'Life':>6} {'Daily':>6} {'Miss':>6}")
    print("-" * 100)
    
    for article in all_articles:
        title = article['title'][:42] + "..." if len(article['title']) > 45 else article['title']
        age = int(article['age_days']) if article['age_days'] else 0
        gap = int(article['gap_days']) if article['gap_days'] else 0
        days_count = article['days_count'] or 0
        lifetime = article['lifetime_reactions'] or 0
        daily = article['daily_reactions'] or 0
        missing = lifetime - daily
        
        print(f"{title:<45} {age:>5}d {gap:>5}d {days_count:>6} {lifetime:>6} {daily:>6} {missing:>6}")
    
    print("\nLégende:")
    print("  Age  = Âge de l'article en jours")
    print("  Gap  = Jours entre publication et première donnée daily")
    print("  Days = Nombre de jours dans daily_analytics")
    print("  Life = Réactions lifetime (article_metrics)")
    print("  Daily= Réactions dans daily_analytics")
    print("  Miss = Réactions manquantes")
    
    conn.close()

if __name__ == "__main__":
    check_daily_analytics_coverage()
