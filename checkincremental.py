#!/usr/bin/env python3
"""
Vérifier si reactions_total est incrémental (par jour) ou cumulatif (total depuis début)
"""

import sqlite3

def check_incremental_vs_cumulative(db_path: str = "devto_metrics.db"):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n" + "="*100)
    print("🔬 TEST: reactions_total est INCRÉMENTAL ou CUMULATIF ?")
    print("="*100)
    
    # Article "Actually Agile"
    article_id = 2969205
    
    cursor.execute("""
        SELECT 
            title,
            published_at
        FROM article_metrics
        WHERE article_id = ?
        LIMIT 1
    """, (article_id,))
    
    info = cursor.fetchone()
    pub_date = info['published_at'][:10]
    
    print(f"\n📊 Article: {info['title'][:60]}")
    print(f"   Publié le: {pub_date}")
    
    # Récupérer les données APRÈS publication
    cursor.execute("""
        SELECT 
            date,
            page_views,
            reactions_total,
            reactions_like,
            reactions_unicorn,
            reactions_readinglist,
            comments_total
        FROM daily_analytics
        WHERE article_id = ?
        AND date >= ?
        ORDER BY date
    """, (article_id, pub_date))
    
    days = cursor.fetchall()
    
    print(f"\n📅 Jours de données depuis publication: {len(days)}")
    
    if not days:
        print("❌ Aucune donnée après publication!")
        return
    
    print(f"\n📊 Échantillon des 15 premiers jours:")
    print(f"{'Date':<12} {'Views':>7} {'Reacts':>8} {'Likes':>7} {'🦄':>5} {'📖':>5} {'💬':>5}")
    print("-" * 70)
    
    for day in days[:15]:
        print(f"{day['date']:<12} {day['page_views']:>7} {day['reactions_total']:>8} "
              f"{day['reactions_like']:>7} {day['reactions_unicorn']:>5} "
              f"{day['reactions_readinglist']:>5} {day['comments_total']:>5}")
    
    # Analyse pour déterminer si c'est incrémental ou cumulatif
    print(f"\n🔍 ANALYSE:")
    
    # Test 1: Est-ce que reactions_total augmente constamment ?
    is_increasing = all(days[i]['reactions_total'] <= days[i+1]['reactions_total'] 
                       for i in range(len(days)-1))
    
    if is_increasing:
        print("   ✅ reactions_total est TOUJOURS croissant → Probablement CUMULATIF")
    else:
        print("   ⚠️  reactions_total n'est PAS toujours croissant → Probablement INCRÉMENTAL")
    
    # Test 2: Comparer MAX vs SUM
    max_reactions = max(d['reactions_total'] for d in days)
    sum_reactions = sum(d['reactions_total'] for d in days)
    
    print(f"\n   MAX(reactions_total): {max_reactions}")
    print(f"   SUM(reactions_total): {sum_reactions}")
    
    # Comparer avec lifetime
    cursor.execute("""
        SELECT reactions
        FROM article_metrics
        WHERE article_id = ?
        ORDER BY collected_at DESC
        LIMIT 1
    """, (article_id,))
    
    lifetime = cursor.fetchone()['reactions']
    print(f"   Lifetime (API):       {lifetime}")
    
    print(f"\n📊 COMPARAISONS:")
    
    if abs(max_reactions - lifetime) <= 2:
        print(f"   ✅ MAX ≈ Lifetime ({max_reactions} ≈ {lifetime})")
        print(f"      → reactions_total est CUMULATIF (total jusqu'à ce jour)")
        print(f"      → Utiliser MAX() est CORRECT")
        
        if max_reactions < lifetime:
            diff = lifetime - max_reactions
            print(f"\n   ⚠️  MAIS il manque {diff} réactions")
            print(f"      → Réactions arrivées après la dernière collecte daily")
            print(f"      → Ou bug dans la synchronisation des données")
    
    elif abs(sum_reactions - lifetime) <= 2:
        print(f"   ✅ SUM ≈ Lifetime ({sum_reactions} ≈ {lifetime})")
        print(f"      → reactions_total est INCRÉMENTAL (nouvelles par jour)")
        print(f"      → Utiliser MAX() est INCORRECT, il faut SUM()")
    
    else:
        print(f"   ❌ Ni MAX ni SUM ne correspondent!")
        print(f"      MAX: {max_reactions}, SUM: {sum_reactions}, Lifetime: {lifetime}")
        print(f"      → Problème de données ou logique complexe")
    
    # Test 3: Regarder la progression jour par jour
    print(f"\n🔍 PROGRESSION DÉTAILLÉE:")
    print(f"   Si CUMULATIF → les valeurs doivent augmenter")
    print(f"   Si INCRÉMENTAL → les valeurs peuvent baisser/rester stables")
    
    print(f"\n   {'Date':<12} {'Reacts':>8} {'Delta':>8} {'Pattern':<20}")
    print("   " + "-" * 60)
    
    for i in range(min(10, len(days))):
        reacts = days[i]['reactions_total']
        if i == 0:
            delta = reacts
            pattern = "Début"
        else:
            delta = reacts - days[i-1]['reactions_total']
            if delta > 0:
                pattern = "↗ Augmente (cumulatif)"
            elif delta == 0:
                pattern = "→ Stable"
            else:
                pattern = "↘ Baisse (impossible si cumulatif!)"
        
        print(f"   {days[i]['date']:<12} {reacts:>8} {delta:>+8} {pattern:<20}")
    
    conn.close()

if __name__ == "__main__":
    check_incremental_vs_cumulative()
