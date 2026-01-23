import os
import sqlite3
import requests
import time
from dotenv import load_dotenv

# Charge les variables du fichier .env
load_dotenv()

# Récupère la clé depuis l'environnement
API_KEY = os.getenv("DEVTO_API_KEY")

if not API_KEY:
    print("❌ Erreur : DEVTO_API_KEY non trouvée dans le fichier .env")
    exit(1)
    
DB_PATH = "devto_metrics.db"

def sync_incremental():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. On récupère la liste de tes articles actifs
    cursor.execute("SELECT DISTINCT article_id, title FROM article_metrics")
    articles = cursor.fetchall()

    new_comments_count = 0

    for art_id, title in articles:
        # On récupère les commentaires (l'API renvoie les plus récents par défaut)
        res = requests.get(f"https://dev.to/api/comments?a_id={art_id}")
        
        if res.status_code == 200:
            comments = res.json()
            for c in comments:
                c_id = c.get('id_code')
                
                # On utilise INSERT OR IGNORE pour ne pas créer de doublons
                # Si le comment_id existe déjà, SQLite passera à la suite
                cursor.execute("""
                    INSERT OR IGNORE INTO comments 
                    (collected_at, comment_id, article_id, article_title, author_username, body_html, created_at)
                    VALUES (CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
                """, (
                    c_id, art_id, title, 
                    c.get('user', {}).get('username'),
                    c.get('body_html'),
                    c.get('created_at')
                ))
                
                if cursor.rowcount > 0:
                    new_comments_count += 1
            
            conn.commit()
        time.sleep(0.2)

    print(f"✅ Synchro terminée. {new_comments_count} nouveaux commentaires ajoutés.")
    conn.close()

if __name__ == "__main__":
    sync_incremental()