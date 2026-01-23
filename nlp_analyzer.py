import os
import spacy
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from dotenv import load_dotenv
from core.database import DatabaseManager

# Charge les variables d'environnement (.env)
load_dotenv()

class NLPAnalyzer:
    def __init__(self, db_path="devto_metrics.db"):
        self.db = DatabaseManager(db_path)
        self.author_id = "pascal_cescato_692b7a8a20"
        self.vader = SentimentIntensityAnalyzer()
        self._setup_db()
        
        try:
            # Modèle léger pour l'extraction de concepts
            self.nlp = spacy.load("en_core_web_sm") 
        except:
            print("❌ Erreur : Modèle spaCy 'en_core_web_sm' manquant.")
            print("👉 Lance : python3 -m spacy download en_core_web_sm")
            exit(1)

    def _setup_db(self):
        """Initialise la table des insights si elle n'existe pas"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comment_insights (
                comment_id TEXT PRIMARY KEY,
                sentiment_score REAL,
                mood TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (comment_id) REFERENCES comments (comment_id)
            )
        """)
        conn.commit()
        conn.close()

    def clean_text(self, html):
        """Nettoie le HTML et retire les blocs de code pour l'analyse"""
        if not html: return ""
        soup = BeautifulSoup(html, "html.parser")
        for code in soup.find_all(['code', 'pre']):
            code.decompose()
        return soup.get_text(separator=' ').strip()

    def is_spam(self, text):
        """Filtre pragmatique contre les bots de casino et arnaques"""
        spam_keywords = ['investigator', 'hack', 'whatsapp', 'kasino', 'slot', '777', 'putar', 'kaya']
        t = text.lower()
        suspicious_patterns = ["🎡", "🎰", "💰"]
        
        if any(p in t for p in suspicious_patterns): return True
        if any(k in t for k in spam_keywords): return True
        if "@" in t and ".com" in t and "gmail" in t: return True
        return False

    def find_unanswered_questions(self):
        """Détecte les questions des lecteurs qui n'ont pas de réponse de ta part"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        query = """
            SELECT q.article_title, q.author_username, q.body_html, q.created_at
            FROM comments q
            WHERE q.body_html LIKE '%?%' 
            AND q.author_username != ?
            AND NOT EXISTS (
                SELECT 1 FROM comments a 
                WHERE a.article_id = q.article_id 
                AND a.author_username = ? 
                AND a.created_at > q.created_at
            )
            ORDER BY q.created_at DESC
        """
        cursor.execute(query, (self.author_id, self.author_id))
        questions = cursor.fetchall()
        conn.close()

        if questions:
            print(f"\n❓ QUESTIONS EN ATTENTE ({len(questions)})")
            print("-" * 80)
            for q in questions:
                text = self.clean_text(q['body_html'])[:120]
                print(f"📘 {q['article_title'][:50]}...")
                print(f"   👤 @{q['author_username']} : \"{text}...\"")
                print(f"   📅 {q['created_at']}\n")
        else:
            print("\n✅ Aucune question en attente. Tu es à jour !")

    def show_stats(self):
        """Affiche le résumé global de l'ambiance"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        print("\n📊 ÉTAT GLOBAL DE L'AUDIENCE (Moteur VADER) :")
        cursor.execute("SELECT mood, COUNT(*) as c FROM comment_insights GROUP BY mood")
        for r in cursor.fetchall():
            print(f"   {r['mood']} : {r['c']}")
        conn.close()

    def run(self):
        """Exécute l'analyse incrémentale"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # On ne traite que les nouveaux commentaires
        query = """
            SELECT c.comment_id, c.article_title, c.body_html 
            FROM comments c
            LEFT JOIN comment_insights i ON c.comment_id = i.comment_id
            WHERE i.comment_id IS NULL AND c.author_username != ?
        """
        cursor.execute(query, (self.author_id,))
        rows = cursor.fetchall()

        if rows:
            print(f"🚀 Analyse VADER de {len(rows)} nouveaux commentaires...")
            for row in rows:
                text = self.clean_text(row['body_html'])
                if text and not self.is_spam(text):
                    vs = self.vader.polarity_scores(text)
                    score = vs['compound']

                    # Application des seuils calibrés
                    if score >= 0.3:
                        mood = "🌟 Positif"
                    elif score <= -0.2:
                        mood = "😟 Négatif"
                    else:
                        mood = "😐 Neutre"
        
                    cursor.execute("""
                        INSERT OR REPLACE INTO comment_insights (comment_id, sentiment_score, mood)
                        VALUES (?, ?, ?)
                    """, (row['comment_id'], score, mood))
            conn.commit()
            print("✅ Mise à jour terminée.")
        else:
            print("☕ Aucun nouveau commentaire à analyser.")

        conn.close()
        
        # Affichage des résultats
        self.show_stats()
        self.find_unanswered_questions()

if __name__ == "__main__":
    analyzer = NLPAnalyzer()
    analyzer.run()