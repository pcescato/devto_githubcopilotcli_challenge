import sqlite3
import requests
import time

API_KEY = "LAPzzxnSm7qNx3cywP9iwatK"
DB_PATH = "devto_metrics.db"

def sync():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # On récupère la liste unique des articles
    cursor.execute("SELECT DISTINCT article_id, title FROM article_metrics")
    articles = cursor.fetchall()

    print(f"🚀 Début de la synchronisation pour {len(articles)} articles...")

    for art_id, title in articles:
        print(f"  📥 Récupération des commentaires pour : {title[:40]}...")
        
        url = f"https://dev.to/api/comments?a_id={art_id}"
        res = requests.get(url)
        
        if res.status_code == 200:
            comments = res.json()
            for c in comments:
                # On insère ou on ignore si déjà là
                cursor.execute("""
                    INSERT OR IGNORE INTO comments 
                    (collected_at, comment_id, article_id, article_title, author_username, body_html, created_at)
                    VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
                """, (
                    c.get('id_code'),
                    art_id,
                    title,
                    c.get('user', {}).get('username'),
                    c.get('body_html'),
                    c.get('created_at')
                ))
            conn.commit()
        else:
            print(f"  ❌ Erreur API pour l'article {art_id}")
        
        time.sleep(0.2) # Courtoisie

    print("✅ Terminé ! Tous les commentaires disponibles sont en base.")
    conn.close()

if __name__ == "__main__":
    sync()
