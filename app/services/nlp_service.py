"""
NLP Service - High-Performance Async Sentiment Analysis & Spam Detection

Refactored from nlp_analyzer.py with modern async PostgreSQL architecture.
- Uses AsyncConnection for all database operations
- Loads spaCy and VADER models once at initialization
- Wraps CPU-bound tasks in asyncio.to_thread() for async compatibility
- Preserves exact sentiment thresholds and spam detection logic
- Processes comments in batches of 50 for optimal performance
"""

import os
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone

import spacy
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sqlalchemy import select, func, and_, exists
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.tables import comments, comment_insights


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NLPService:
    """
    Modern async NLP service for sentiment analysis and spam detection
    
    Preserves exact business logic from nlp_analyzer.py:
    - VADER sentiment thresholds: >=0.3 positive, <=-0.2 negative
    - Spam detection keywords and emoji patterns
    - BeautifulSoup cleaning for <code> and <pre> blocks
    - Incremental processing with LEFT JOIN ... IS NULL pattern
    """
    
    def __init__(
        self,
        engine: Optional[AsyncEngine] = None,
        db_url: Optional[str] = None,
        author_username: Optional[str] = None,
        batch_size: int = 50
    ):
        """
        Initialize NLP service with pre-loaded models
        
        Args:
            engine: Existing AsyncEngine (preferred)
            db_url: Database URL if engine not provided
            author_username: Your DEV.to username for filtering
            batch_size: Number of comments to process per batch (default: 50)
        """
        # Database setup
        if engine:
            self.engine = engine
        elif db_url:
            self.engine = create_async_engine(
                db_url,
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
                echo=False,
            )
        else:
            self.engine = self._create_engine_from_env()
        
        self.author_username = author_username or os.getenv('DEVTO_USERNAME', 'pascal_cescato_692b7a8a20')
        self.batch_size = batch_size
        
        # Load NLP models once (expensive operations)
        logger.info("🔧 Loading NLP models...")
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("✅ spaCy model loaded: en_core_web_sm")
        except OSError:
            logger.error("❌ Error: spaCy model 'en_core_web_sm' not found.")
            logger.error("👉 Run: python3 -m spacy download en_core_web_sm")
            raise
        
        self.vader = SentimentIntensityAnalyzer()
        logger.info("✅ VADER sentiment analyzer loaded")
        
        # Spam detection configuration (preserved from nlp_analyzer.py:52-58)
        self.spam_keywords = [
            'investigator', 'hack', 'whatsapp', 'kasino', 'slot', '777', 'putar', 'kaya', 'investigator', 'hack', 'whatsapp', 'kasino', 'slot', '777', 'crypto', 'wallet', 'recovery', 'swindled'
        ]
        self.spam_patterns = ["🎡", "🎰", "💰"]
    
    def _create_engine_from_env(self) -> AsyncEngine:
        """Create async engine from environment variables"""
        # Load environment variables from .env file
        load_dotenv()
        
        host = os.getenv('POSTGRES_HOST', 'localhost')
        port = os.getenv('POSTGRES_PORT', '5432')
        database = os.getenv('POSTGRES_DB', 'devto_analytics')
        user = os.getenv('POSTGRES_USER')
        password = os.getenv('POSTGRES_PASSWORD')
        
        if not user or not password:
            raise ValueError(
                "Missing required environment variables: POSTGRES_USER and POSTGRES_PASSWORD"
            )
        
        db_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
        return create_async_engine(
            db_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
    
    # ========================================================================
    # TEXT PROCESSING (CPU-BOUND - wrapped in asyncio.to_thread)
    # ========================================================================
    
    @staticmethod
    def clean_text(html: Optional[str]) -> str:
        """
        Clean HTML and remove code blocks before analysis
        
        Preserves exact logic from nlp_analyzer.py:42-48
        Uses BeautifulSoup to strip <code> and <pre> tags
        
        Args:
            html: HTML string from comment body
        
        Returns:
            Cleaned plain text
        """
        if not html:
            return ""
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove code blocks (they skew sentiment analysis)
        for code in soup.find_all(['code', 'pre']):
            code.decompose()
        
        return soup.get_text(separator=' ').strip()
    
    def is_spam(self, text: str) -> bool:
        """
        Pragmatic spam filter for casino bots and scams
        
        Preserves exact logic from nlp_analyzer.py:50-59
        
        Detection patterns:
        - Spam keywords: investigator, hack, whatsapp, kasino, slot, etc.
        - Suspicious emojis: 🎡 🎰 💰
        - Gmail phishing pattern: @ + .com + gmail
        
        Args:
            text: Cleaned comment text
        
        Returns:
            True if spam detected
        """
        if not text:
            return False
        
        t = text.lower()
        
        # Check emoji patterns
        if any(pattern in t for pattern in self.spam_patterns):
            return True
        
        # Check spam keywords
        if any(keyword in t for keyword in self.spam_keywords):
            return True
        
        # Gmail phishing pattern
        if "@" in t and ".com" in t and "gmail" in t:
            return True
        
        return False
    
    async def analyze_sentiment(self, text: str) -> Tuple[float, str]:
        """
        Analyze sentiment using VADER with calibrated thresholds
        
        Preserves exact logic from nlp_analyzer.py:123-132
        
        Thresholds (STRICT PERFECTION):
        - >= 0.3: "🌟 Positif" (Positive)
        - <= -0.2: "😟 Négatif" (Negative)
        - else: "😐 Neutre" (Neutral)
        
        Args:
            text: Cleaned comment text
        
        Returns:
            Tuple of (compound_score, mood_emoji)
        """
        if not text:
            return 0.0, "😐 Neutre"
        
        # VADER is CPU-bound, run in thread pool
        def _vader_analysis():
            return self.vader.polarity_scores(text)
        
        scores = await asyncio.to_thread(_vader_analysis)
        compound_score = scores['compound']
        
        # Apply calibrated thresholds (EXACT from nlp_analyzer.py:127-132)
        if compound_score >= 0.3:
            mood = "🌟 Positif"
        elif compound_score <= -0.2:
            mood = "😟 Négatif"
        else:
            mood = "😐 Neutre"
        
        return compound_score, mood
    
    async def extract_entities(self, text: str) -> List[Dict[str, str]]:
        """
        Extract named entities using spaCy (optional advanced feature)
        
        CPU-bound operation wrapped in asyncio.to_thread()
        
        Args:
            text: Cleaned comment text
        
        Returns:
            List of entities with text and label
        """
        if not text:
            return []
        
        def _spacy_ner():
            doc = self.nlp(text[:1000])  # Limit length for performance
            return [
                {"text": ent.text, "label": ent.label_}
                for ent in doc.ents
            ]
        
        try:
            entities = await asyncio.to_thread(_spacy_ner)
            return entities
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            return []
    
    # ========================================================================
    # DATABASE OPERATIONS (ASYNC)
    # ========================================================================
    
    async def process_pending_comments(self, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Process comments that lack entries in comment_insights
        
        Preserves incremental processing pattern from nlp_analyzer.py:109-116:
        LEFT JOIN comment_insights WHERE insights.comment_id IS NULL
        
        Processes in batches for optimal performance
        Uses INSERT ... ON CONFLICT DO UPDATE for idempotency
        
        Args:
            limit: Max comments to process (None = all pending)
        
        Returns:
            Dict with counts: processed, spam, positive, negative, neutral
        """
        logger.info(f"🚀 Starting sentiment analysis (batch size: {self.batch_size})...")
        
        # Query for pending comments (LEFT JOIN ... IS NULL pattern)
        query = (
            select(
                comments.c.comment_id,
                comments.c.article_title,
                comments.c.body_html,
                comments.c.author_username,
            )
            .select_from(
                comments.outerjoin(
                    comment_insights,
                    comments.c.comment_id == comment_insights.c.comment_id
                )
            )
            .where(
                and_(
                    comment_insights.c.comment_id.is_(None),  # Not yet analyzed
                    comments.c.author_username != self.author_username  # Exclude self
                )
            )
        )
        
        if limit:
            query = query.limit(limit)
        
        # Fetch pending comments
        async with self.engine.connect() as conn:
            result = await conn.execute(query)
            pending = result.mappings().all()
        
        if not pending:
            logger.info("☕ No new comments to analyze.")
            return {
                'processed': 0,
                'spam': 0,
                'positive': 0,
                'negative': 0,
                'neutral': 0
            }
        
        logger.info(f"📊 Found {len(pending)} pending comments")
        
        # Process in batches
        counts = {'processed': 0, 'spam': 0, 'positive': 0, 'negative': 0, 'neutral': 0}
        
        for i in range(0, len(pending), self.batch_size):
            batch = pending[i:i + self.batch_size]
            batch_results = await self._process_batch(batch)
            
            # Update counts
            for key in counts:
                counts[key] += batch_results.get(key, 0)
            
            logger.info(f"✅ Processed batch {i//self.batch_size + 1}/{(len(pending) + self.batch_size - 1)//self.batch_size} "
                       f"({batch_results['processed']} comments)")
        
        logger.info(f"🎉 Analysis complete: {counts['processed']} comments processed")
        logger.info(f"   Spam: {counts['spam']}, Positive: {counts['positive']}, "
                   f"Negative: {counts['negative']}, Neutral: {counts['neutral']}")
        
        return counts
    
    async def _process_batch(self, batch: List[Dict]) -> Dict[str, int]:
        """
        Process a batch of comments with sentiment analysis
        
        Args:
            batch: List of comment dictionaries
        
        Returns:
            Dict with counts for this batch
        """
        counts = {'processed': 0, 'spam': 0, 'positive': 0, 'negative': 0, 'neutral': 0}
        analyzed_at = datetime.now(timezone.utc)
        
        async with self.engine.begin() as conn:
            for comment in batch:
                # Clean HTML
                text = self.clean_text(comment['body_html'])
                
                if not text:
                    continue
                
                # Spam detection
                spam_detected = self.is_spam(text)
                if spam_detected:
                    counts['spam'] += 1
                    # Still store spam results for tracking
                    stmt = pg_insert(comment_insights).values(
                        comment_id=comment['comment_id'],
                        sentiment_score=0.0,
                        mood="🚫 Spam",
                        is_spam=True,
                        analyzed_at=analyzed_at,
                    )
                    stmt = stmt.on_conflict_do_update(
                        constraint='pk_comment_insights',
                        set_={
                            'is_spam': True,
                            'mood': "🚫 Spam",
                            'analyzed_at': analyzed_at,
                        }
                    )
                    await conn.execute(stmt)
                    counts['processed'] += 1
                    continue
                
                # Sentiment analysis
                score, mood = await self.analyze_sentiment(text)
                
                # Count mood
                if "Positif" in mood:
                    counts['positive'] += 1
                elif "Négatif" in mood:
                    counts['negative'] += 1
                else:
                    counts['neutral'] += 1
                
                # Optional: Extract named entities (can be slow)
                # entities = await self.extract_entities(text)
                
                # Insert with ON CONFLICT DO UPDATE for idempotency
                stmt = pg_insert(comment_insights).values(
                    comment_id=comment['comment_id'],
                    sentiment_score=score,
                    mood=mood,
                    is_spam=False,
                    analyzed_at=analyzed_at,
                    # named_entities=entities if entities else None,
                )
                
                stmt = stmt.on_conflict_do_update(
                    constraint='pk_comment_insights',
                    set_={
                        'sentiment_score': stmt.excluded.sentiment_score,
                        'mood': stmt.excluded.mood,
                        'is_spam': False,
                        'analyzed_at': stmt.excluded.analyzed_at,
                    }
                )
                
                await conn.execute(stmt)
                counts['processed'] += 1
        
        return counts
    
    async def get_sentiment_stats(self) -> Dict[str, Any]:
        """
        Get global sentiment statistics
        
        Replaces: show_stats() from nlp_analyzer.py:93-101
        
        Returns:
            Dict with mood counts and percentages
        """
        query = (
            select(
                comment_insights.c.mood,
                func.count().label('count')
            )
            .where(comment_insights.c.is_spam == False)
            .group_by(comment_insights.c.mood)
            .order_by(func.count().desc())
        )
        
        async with self.engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        
        total = sum(row['count'] for row in rows)
        stats = {
            'total': total,
            'moods': []
        }
        
        for row in rows:
            percentage = (row['count'] / total * 100) if total > 0 else 0
            stats['moods'].append({
                'mood': row['mood'],
                'count': row['count'],
                'percentage': round(percentage, 1)
            })
        
        return stats
    
    async def find_unanswered_questions(self) -> List[Dict[str, Any]]:
        """
        Detect reader questions without author responses
        
        Preserves exact logic from nlp_analyzer.py:61-91
        
        Pattern: Find comments with '?' that don't have a subsequent
        reply from the author on the same article
        
        Returns:
            List of unanswered question dictionaries
        """
        # Create alias ONCE (reuse it to avoid duplicate alias error)
        comments_reply = comments.alias('reply')
        
        # Subquery: Check if author replied after the question
        has_reply = exists().where(
            and_(
                comments_reply.c.article_id == comments.c.article_id,
                comments_reply.c.author_username == self.author_username,
                comments_reply.c.created_at > comments.c.created_at
            )
        )
        
        # Main query: Questions without author response
        query = (
            select(
                comments.c.comment_id,
                comments.c.article_title,
                comments.c.author_username,
                comments.c.body_html,
                comments.c.created_at,
            )
            .where(
                and_(
                    comments.c.body_html.contains('?'),  # Contains question mark
                    comments.c.author_username != self.author_username,  # Not from author
                    ~has_reply  # NOT EXISTS
                )
            )
            .order_by(comments.c.created_at.desc())
        )
        
        async with self.engine.connect() as conn:
            result = await conn.execute(query)
            rows = result.mappings().all()
        
        questions = []
        for row in rows:
            text = self.clean_text(row['body_html'])
            questions.append({
                'comment_id': row['comment_id'],
                'article_title': row['article_title'],
                'author_username': row['author_username'],
                'text_preview': text[:120] + "..." if len(text) > 120 else text,
                'created_at': row['created_at'],
            })
        
        return questions
    
    # ========================================================================
    # HIGH-LEVEL ORCHESTRATION
    # ========================================================================
    
    async def run_analysis(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Run complete NLP analysis pipeline
        
        Replaces: run() from nlp_analyzer.py:103-147
        
        Steps:
        1. Process pending comments with sentiment analysis
        2. Get sentiment statistics
        3. Find unanswered questions
        
        Args:
            limit: Max comments to process (None = all)
        
        Returns:
            Complete analysis results
        """
        logger.info("\n" + "="*80)
        logger.info("🧠 NLP ANALYSIS PIPELINE")
        logger.info("="*80 + "\n")
        
        # Step 1: Process pending comments
        process_results = await self.process_pending_comments(limit=limit)
        
        # Step 2: Get sentiment stats
        stats = await self.get_sentiment_stats()
        
        # Step 3: Find unanswered questions
        questions = await self.find_unanswered_questions()
        
        return {
            'processing': process_results,
            'sentiment_stats': stats,
            'unanswered_questions': questions,
        }
    
    def print_results(self, results: Dict[str, Any]):
        """Pretty print analysis results"""
        print("\n" + "="*80)
        print("📊 ÉTAT GLOBAL DE L'AUDIENCE (Moteur VADER)")
        print("="*80)
        
        stats = results['sentiment_stats']
        for mood_data in stats['moods']:
            print(f"   {mood_data['mood']:<20} : {mood_data['count']:>5} ({mood_data['percentage']:>5.1f}%)")
        print(f"\n   Total analyzed: {stats['total']}")
        
        print("\n" + "="*80)
        questions = results['unanswered_questions']
        if questions:
            print(f"❓ QUESTIONS EN ATTENTE ({len(questions)})")
            print("="*80)
            for q in questions[:10]:  # Show first 10
                print(f"\n📘 {q['article_title'][:50]}...")
                print(f"   👤 @{q['author_username']}")
                print(f"   💬 \"{q['text_preview']}\"")
                print(f"   📅 {q['created_at']}")
            if len(questions) > 10:
                print(f"\n   ... and {len(questions) - 10} more questions")
        else:
            print("✅ Aucune question en attente. Tu es à jour !")
        
        print("\n" + "="*80 + "\n")


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def create_nlp_service(
    engine: Optional[AsyncEngine] = None,
    author_username: Optional[str] = None
) -> NLPService:
    """
    Create NLPService instance
    
    Args:
        engine: Optional existing AsyncEngine
        author_username: Your DEV.to username
    
    Returns:
        Initialized NLPService
    """
    return NLPService(engine=engine, author_username=author_username)


async def main():
    """CLI entry point"""
    import sys
    
    # Create service
    service = await create_nlp_service()
    
    # Parse arguments
    limit = None
    if len(sys.argv) > 1 and sys.argv[1].startswith('--limit='):
        limit = int(sys.argv[1].split('=')[1])
    
    # Run analysis
    try:
        results = await service.run_analysis(limit=limit)
        service.print_results(results)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
