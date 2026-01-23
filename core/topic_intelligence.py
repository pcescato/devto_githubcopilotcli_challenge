#!/usr/bin/env python3
import json
import re
from collections import Counter
from core.database import DatabaseManager

class TopicIntelligence:
    def __init__(self, db_path="devto_metrics.db"):
        self.db = DatabaseManager(db_path)
        # Defining your areas of expertise (your DNA)
        self.themes = {
            "Expertise Tech": ["sql", "database", "python", "cloud", "docker", "vps", "astro", "hugo", "vector", "cte"],
            "Human & Career": ["cv", "career", "feedback", "developer", "learning", "growth"],
            "Culture & Agile": ["agile", "scrum", "performance", "theater", "laziness", "management"]
        }

    def _get_article_theme(self, title, tags):
        """Identifie le thème dominant d'un article."""
        text = (title + " " + tags).lower()
        scores = {theme: 0 for theme in self.themes}
        
        for theme, keywords in self.themes.items():
            for kw in keywords:
                if kw in text:
                    scores[theme] += 1
        
        # We return the theme with the most matches, or 'Other'
        max_theme = max(scores, key=scores.get)
        return max_theme if scores[max_theme] > 0 else "Free Exploration"

    def analyze_dna(self):
        """Génère le miroir d'impact de ton contenu."""
        conn = self.db.get_connection()
        articles = conn.execute("""
            SELECT article_id, title, tags, MAX(views) as views, MAX(reactions) as reactions 
            FROM article_metrics GROUP BY article_id
        """).fetchall()

        dna_report = {theme: {"count": 0, "views": 0, "reactions": 0} for theme in self.themes}
        dna_report["Free Exploration"] = {"count": 0, "views": 0, "reactions": 0}

        for art in articles:
            theme = self._get_article_theme(art['title'], art['tags'] or "")
            dna_report[theme]["count"] += 1
            dna_report[theme]["views"] += art['views']
            dna_report[theme]["reactions"] += art['reactions']

        print("\n" + "🧬" + " --- AUTHOR CONTENT DNA (MIRROR REPORT) ---")
        print("=" * 80)
        print(f"{'Thematic Axis':<25} {'Articles':<10} {'Avg Views':<12} {'Engagement %':<12}")
        print("-" * 80)

        for theme, stats in dna_report.items():
            if stats['count'] > 0:
                avg_views = stats['views'] / stats['count']
                engage = (stats['reactions'] / stats['views'] * 100) if stats['views'] > 0 else 0
                print(f"{theme:<25} {stats['count']:<10} {avg_views:<12.0f} {engage:<12.2f}%")

        print("\n💡 PRAGMATIC INTERPRETATION:")
        # Best engagement
        best_engage = max(dna_report, key=lambda x: (dna_report[x]['reactions']/dna_report[x]['views'] if dna_report[x]['views'] > 0 else 0))
        print(f"👉 Your community engages most intensely with the '{best_engage}' axis.")
        
        # Best views
        best_views = max(dna_report, key=lambda x: (dna_report[x]['views']/dna_report[x]['count'] if dna_report[x]['count'] > 0 else 0))
        print(f"👉 The '{best_views}' axis is your strongest driver for raw visibility.")

if __name__ == "__main__":
    TopicIntelligence().analyze_dna()