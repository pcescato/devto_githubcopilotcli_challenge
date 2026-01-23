import sqlite3
import os
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="devto_metrics.db"):
        self.db_path = db_path
        self._run_migrations()

    def get_connection(self):
        """Retourne une connexion avec row_factory pour accès par nom de colonne."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _run_migrations(self):
        """Assure que le schéma est à jour sans casser les données existantes."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. Migration article_metrics : ajout de is_deleted
        try:
            cursor.execute("SELECT is_deleted FROM article_metrics LIMIT 1")
        except sqlite3.OperationalError:
            print("🔧 Migration : Ajout de 'is_deleted' dans article_metrics...")
            cursor.execute("ALTER TABLE article_metrics ADD COLUMN is_deleted INTEGER DEFAULT 0")

        # 2. Table historique : Création avec edited_at_api
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS article_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                title TEXT,
                slug TEXT,
                tags TEXT,
                content_hash TEXT,
                edited_at_api TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration historique : ajout de edited_at_api si la table existait déjà sans
        try:
            cursor.execute("SELECT edited_at_api FROM article_history LIMIT 1")
        except sqlite3.OperationalError:
            print("🔧 Migration : Ajout de 'edited_at_api' dans article_history...")
            cursor.execute("ALTER TABLE article_history ADD COLUMN edited_at_api TEXT")

        # 3. Table des événements marquants (Milestones)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS milestone_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                event_type TEXT, 
                description TEXT,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    # --- MÉTHODES UTILITAIRES ---

    def log_milestone(self, article_id, event_type, description, conn=None):
        """Enregistre un événement (changement de titre, curation staff, etc.)"""
        should_close = conn is None
        if conn is None:
            conn = self.get_connection()
        
        conn.execute(
            "INSERT INTO milestone_events (article_id, event_type, description) VALUES (?, ?, ?)",
            (article_id, event_type, description)
        )
        
        if should_close:
            conn.commit()
            conn.close()

    def get_all_active_articles(self):
        """Récupère la liste propre pour list_articles.py."""
        query = """
            SELECT article_id, title, slug, MAX(views) as total_views, MAX(published_at) as published_at
            FROM article_metrics 
            WHERE is_deleted = 0 
            GROUP BY article_id 
            ORDER BY published_at DESC
        """
        with self.get_connection() as conn:
            return conn.execute(query).fetchall()

    def get_latest_article_snapshot(self, article_id):
        """Détails pour un article spécifique."""
        query = "SELECT * FROM article_metrics WHERE article_id = ? ORDER BY collected_at DESC LIMIT 1"
        with self.get_connection() as conn:
            return conn.execute(query, (article_id,)).fetchone()