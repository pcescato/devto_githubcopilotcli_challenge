"""
DEV.to Analytics Platform - PostgreSQL 18 Schema
SQLAlchemy Core Table Definitions

This schema preserves all business logic patterns from the SQLite implementation:
- Proximity search using ABS() for closest timestamp matching
- Incremental processing via LEFT JOIN ... IS NULL pattern
- INSERT ON CONFLICT for idempotent operations
- 7-day follower attribution window with 6-hour tolerance
- Quality score: (completion × 0.7) + (min(engagement, 20) × 1.5)
- Sentiment thresholds: >=0.3 positive, <=-0.2 negative

Key PostgreSQL 18 features:
- JSONB for flexible metadata
- ARRAY types for lists
- pgvector for embeddings (Vector(1536))
- Table partitioning for daily_analytics
- GiST indexes for full-text search
- Proper foreign key cascades
"""

from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    Boolean,
    ForeignKey,
    Index,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone


# Metadata object - shared across all tables
metadata = MetaData(
    schema='devto_analytics',
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
)


# ============================================================================
# CORE METRICS TABLES
# ============================================================================

snapshots = Table(
    'snapshots',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('collected_at', DateTime(timezone=True), nullable=False, index=True),
    Column('total_articles', Integer, nullable=True),
    Column('total_views', Integer, nullable=True),
    Column('total_reactions', Integer, nullable=True),
    Column('total_comments', Integer, nullable=True),
    Column('follower_count', Integer, nullable=True),
    
    UniqueConstraint('collected_at', name='uq_snapshots_collected_at'),
    
    comment='Global snapshot of account metrics at collection time'
)


article_metrics = Table(
    'article_metrics',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('collected_at', DateTime(timezone=True), nullable=False, index=True),
    Column('article_id', Integer, nullable=False, index=True),
    Column('title', Text, nullable=True),
    Column('slug', String(255), nullable=True),
    Column('published_at', DateTime(timezone=True), nullable=True, index=True),
    Column('views', Integer, default=0),
    Column('reactions', Integer, default=0),
    Column('comments', Integer, default=0),
    Column('reading_time_minutes', Integer, nullable=True),
    
    # JSONB for flexible tag storage
    Column('tags', JSONB, nullable=True, comment='Full tag metadata as JSON'),
    
    # ARRAY for simple tag list (preserves SQLite tags TEXT column)
    Column('tag_list', ARRAY(String), nullable=True, comment='Simple array of tag names'),
    
    # Soft delete flag (preserves SQLite is_deleted column)
    Column('is_deleted', Boolean, default=False, nullable=False),
    
    UniqueConstraint('collected_at', 'article_id', name='uq_article_metrics_collected_article'),
    
    comment='Time-series snapshots of article performance (NOT unique per article)'
)

# Indexes for article_metrics
Index('ix_article_metrics_article_published', article_metrics.c.article_id, article_metrics.c.published_at)
Index('ix_article_metrics_views', article_metrics.c.views)
Index('ix_article_metrics_active', article_metrics.c.is_deleted, postgresql_where=(article_metrics.c.is_deleted == False))


follower_events = Table(
    'follower_events',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('collected_at', DateTime(timezone=True), nullable=False, unique=True, index=True),
    Column('follower_count', Integer, nullable=False),
    Column('new_followers_since_last', Integer, nullable=True, 
           comment='Delta from previous snapshot (business logic in devto_tracker.py:133-143)'),
    
    comment='Follower count tracking with delta calculation for attribution analysis'
)


comments = Table(
    'comments',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('collected_at', DateTime(timezone=True), nullable=False, index=True),
    Column('comment_id', String(50), unique=True, nullable=False, 
           comment='DEV.to comment ID (e.g., "abc123") - used for INSERT OR IGNORE pattern'),
    Column('article_id', Integer, ForeignKey('devto_analytics.article_metrics.article_id', ondelete='CASCADE'), 
           nullable=False, index=True),
    Column('article_title', Text, nullable=True),
    Column('created_at', DateTime(timezone=True), nullable=True),
    Column('author_username', String(100), nullable=True, index=True),
    Column('author_name', String(255), nullable=True),
    
    # Multiple body formats for different use cases
    Column('body_html', Text, nullable=True, comment='Original HTML from API'),
    Column('body_text', Text, nullable=True, comment='Plain text extracted from HTML'),
    Column('body_markdown', Text, nullable=True, comment='Markdown format if available'),
    Column('body_length', Integer, nullable=True, comment='Character count for engagement metrics'),
    
    comment='All comments across all articles - INSERT OR IGNORE for idempotency'
)

# Indexes for comments
Index('ix_comments_article_author', comments.c.article_id, comments.c.author_username)
Index('ix_comments_created', comments.c.created_at)


followers = Table(
    'followers',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('collected_at', DateTime(timezone=True), nullable=False, index=True),
    Column('follower_id', Integer, unique=True, nullable=False),
    Column('username', String(100), nullable=True),
    Column('name', String(255), nullable=True),
    Column('followed_at', DateTime(timezone=True), nullable=True),
    Column('profile_image', Text, nullable=True),
    
    comment='Individual follower records from paginated API'
)


# ============================================================================
# RICH ANALYTICS TABLES (from undocumented endpoints)
# ============================================================================

daily_analytics = Table(
    'daily_analytics',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('article_id', Integer, ForeignKey('devto_analytics.article_metrics.article_id', ondelete='CASCADE'), 
           nullable=False, index=True),
    Column('date', DateTime(timezone=True), nullable=False, index=True, 
           comment='Date of analytics (partition key)'),
    Column('collected_at', DateTime(timezone=True), nullable=False, 
           comment='When this data was collected'),
    
    # View metrics
    Column('page_views', Integer, default=0),
    Column('average_read_time_seconds', Integer, default=0, 
           comment='Used for completion rate: (avg_read / expected_time) * 100'),
    Column('total_read_time_seconds', Integer, default=0),
    
    # Reaction breakdown (from /analytics/historical)
    Column('reactions_total', Integer, default=0),
    Column('reactions_like', Integer, default=0, comment='Heart reactions'),
    Column('reactions_readinglist', Integer, default=0, comment='Bookmark/save'),
    Column('reactions_unicorn', Integer, default=0, comment='Unicorn/special'),
    
    # Engagement metrics
    Column('comments_total', Integer, default=0),
    Column('follows_total', Integer, default=0, 
           comment='New followers attributed to this article on this day'),
    
    UniqueConstraint('article_id', 'date', name='uq_daily_analytics_article_date'),
    
    comment='''
    Daily breakdown from /api/analytics/historical (undocumented)
    ⚠️ DATA PERIOD: Last 90 days only from DEV.to API
    Used for: Quality scores, read time analysis, reaction breakdown
    Pattern: INSERT OR REPLACE for reprocessing
    '''
)

# Indexes for daily_analytics
Index('ix_daily_analytics_article_date', daily_analytics.c.article_id, daily_analytics.c.date)
Index('ix_daily_analytics_collected', daily_analytics.c.collected_at)

# Note: Partitioning would be done with PostgreSQL DDL:
# CREATE TABLE daily_analytics_YYYY_MM PARTITION OF daily_analytics
# FOR VALUES FROM ('YYYY-MM-01') TO ('YYYY-MM+1-01');


referrers = Table(
    'referrers',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('article_id', Integer, ForeignKey('devto_analytics.article_metrics.article_id', ondelete='CASCADE'), 
           nullable=False, index=True),
    Column('domain', String(255), nullable=False, index=True, 
           comment='Traffic source domain (e.g., google.com, twitter.com)'),
    Column('count', Integer, nullable=False, default=0),
    Column('collected_at', DateTime(timezone=True), nullable=False),
    
    UniqueConstraint('article_id', 'domain', 'collected_at', name='uq_referrers_article_domain_time'),
    
    comment='Traffic sources from /api/analytics/referrers (undocumented)'
)

# Indexes for referrers
Index('ix_referrers_domain_count', referrers.c.domain, referrers.c.count)


# ============================================================================
# CONTENT TABLES (from content_collector.py)
# ============================================================================

article_content = Table(
    'article_content',
    metadata,
    Column('article_id', Integer, 
           ForeignKey('devto_analytics.article_metrics.article_id', ondelete='CASCADE'), 
           primary_key=True, comment='One content record per article'),
    Column('body_markdown', Text, nullable=False, comment='Full markdown source'),
    Column('body_html', Text, nullable=True, comment='Rendered HTML'),
    
    # Content metrics (from parse_markdown)
    Column('word_count', Integer, nullable=True, 
           comment='Word count excluding code blocks'),
    Column('char_count', Integer, nullable=True),
    Column('code_blocks_count', Integer, nullable=True),
    Column('links_count', Integer, nullable=True),
    Column('images_count', Integer, nullable=True),
    Column('headings_count', Integer, nullable=True),
    
    # NLP/Vector storage
    Column('embedding', Vector(1536), nullable=True, 
           comment='OpenAI ada-002 embedding for semantic search'),
    Column('keywords', JSONB, nullable=True, 
           comment='Extracted keywords with scores'),
    Column('main_topics', ARRAY(String), nullable=True, 
           comment='Topic classification results'),
    
    # Collection metadata
    Column('collected_at', DateTime(timezone=True), nullable=False),
    
    comment='Full article content for NLP analysis and semantic search'
)

# GiST index for vector similarity search
Index('ix_article_content_embedding', article_content.c.embedding, 
      postgresql_using='ivfflat', postgresql_with={'lists': 100})


article_code_blocks = Table(
    'article_code_blocks',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('article_id', Integer, 
           ForeignKey('devto_analytics.article_content.article_id', ondelete='CASCADE'), 
           nullable=False, index=True),
    Column('language', String(50), nullable=True, 
           comment='Programming language (extracted from ```language marker)'),
    Column('code_text', Text, nullable=True),
    Column('line_count', Integer, nullable=True),
    Column('block_order', Integer, nullable=True, 
           comment='Sequential order in article (1, 2, 3...)'),
    
    comment='''
    Code blocks extracted via regex: ```(language)?\\n(.*?)```
    Pattern from content_collector.py:208-219
    '''
)

Index('ix_code_blocks_language', article_code_blocks.c.language)


article_links = Table(
    'article_links',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('article_id', Integer, 
           ForeignKey('devto_analytics.article_content.article_id', ondelete='CASCADE'), 
           nullable=False, index=True),
    Column('url', Text, nullable=False),
    Column('link_text', Text, nullable=True, comment='Anchor text from [text](url)'),
    Column('link_type', String(20), nullable=True, 
           comment='anchor|internal|external|relative (classified in content_collector.py:228-237)'),
    
    comment='All links extracted from markdown: [text](url)'
)

Index('ix_links_type', article_links.c.link_type)


# ============================================================================
# ANALYSIS TABLES (NLP, sentiment, tracking)
# ============================================================================

comment_insights = Table(
    'comment_insights',
    metadata,
    Column('comment_id', String(50), 
           ForeignKey('devto_analytics.comments.comment_id', ondelete='CASCADE'), 
           primary_key=True),
    
    # VADER sentiment analysis results
    Column('sentiment_score', Float, nullable=True, 
           comment='VADER compound score: -1.0 to +1.0'),
    Column('mood', String(50), nullable=True, 
           comment='''
           Calibrated thresholds (nlp_analyzer.py:127-132):
           >= 0.3: "🌟 Positif"
           <= -0.2: "😟 Négatif"
           else: "😐 Neutre"
           '''),
    
    # Spam detection
    Column('is_spam', Boolean, default=False, 
           comment='Detected via nlp_analyzer.py:50-59 (casino keywords, suspicious patterns)'),
    
    # Analysis metadata
    Column('analyzed_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    
    # Additional NLP features
    Column('named_entities', JSONB, nullable=True, comment='spaCy NER results'),
    Column('key_phrases', ARRAY(String), nullable=True),
    
    comment='''
    Sentiment analysis via VADER + spaCy
    Incremental processing: LEFT JOIN ... WHERE insights.comment_id IS NULL
    Pattern: nlp_analyzer.py:109-116
    '''
)


article_history = Table(
    'article_history',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('article_id', Integer, 
           ForeignKey('devto_analytics.article_metrics.article_id', ondelete='CASCADE'), 
           nullable=False, index=True),
    Column('title', Text, nullable=True),
    Column('slug', String(255), nullable=True),
    Column('tags', Text, nullable=True, comment='Comma-separated tag string (legacy)'),
    Column('tag_list', ARRAY(String), nullable=True, comment='Array of tags'),
    Column('content_hash', String(64), nullable=True, comment='SHA-256 of markdown for change detection'),
    
    # Timestamps
    Column('changed_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    Column('edited_at_api', String(100), nullable=True, 
           comment='edited_at timestamp from DEV.to API if available'),
    
    comment='''
    Content change tracking (title, tags, content)
    Used by ContentTracker (content_tracker.py:20-53)
    Triggers milestone_events on title changes
    '''
)

Index('ix_article_history_article_changed', article_history.c.article_id, article_history.c.changed_at)


milestone_events = Table(
    'milestone_events',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('article_id', Integer, 
           ForeignKey('devto_analytics.article_metrics.article_id', ondelete='SET NULL'), 
           nullable=True, index=True, 
           comment='NULL for account-level events'),
    Column('event_type', String(50), nullable=False, 
           comment='title_change, featured, top_7, reached_1k_views, etc.'),
    Column('description', Text, nullable=True),
    Column('occurred_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    
    # Velocity impact (for correlation analysis)
    Column('velocity_before', Float, nullable=True, comment='Views/hour before event'),
    Column('velocity_after', Float, nullable=True, comment='Views/hour after event'),
    
    comment='''
    Significant events for velocity correlation analysis
    Pattern: advanced_analytics.py:79-116
    Logged via DatabaseManager.log_milestone()
    '''
)

Index('ix_milestone_events_type', milestone_events.c.event_type)
Index('ix_milestone_events_occurred', milestone_events.c.occurred_at)


# ============================================================================
# AUTHOR DNA / TOPIC INTELLIGENCE
# ============================================================================

author_themes = Table(
    'author_themes',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('theme_name', String(100), nullable=False, unique=True, 
           comment='E.g., "Expertise Tech", "Human & Career"'),
    Column('keywords', ARRAY(String), nullable=False, 
           comment='Keywords that identify this theme'),
    Column('description', Text, nullable=True),
    Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    
    comment='''
    Theme definitions for author DNA analysis
    Based on topic_intelligence.py:11-15
    Used to classify articles into content pillars
    '''
)


article_theme_mapping = Table(
    'article_theme_mapping',
    metadata,
    Column('article_id', Integer, 
           ForeignKey('devto_analytics.article_metrics.article_id', ondelete='CASCADE'), 
           nullable=False),
    Column('theme_id', Integer, 
           ForeignKey('devto_analytics.author_themes.id', ondelete='CASCADE'), 
           nullable=False),
    Column('confidence_score', Float, nullable=True, 
           comment='Match confidence: keyword_matches / total_keywords'),
    Column('matched_keywords', ARRAY(String), nullable=True),
    Column('classified_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    
    UniqueConstraint('article_id', 'theme_id', name='uq_article_theme_article_theme'),
    
    comment='Article → Theme classification results from topic_intelligence.py'
)

Index('ix_article_theme_article', article_theme_mapping.c.article_id)
Index('ix_article_theme_theme', article_theme_mapping.c.theme_id)


# ============================================================================
# ANALYTICS CACHE (for dashboard performance)
# ============================================================================

article_stats_cache = Table(
    'article_stats_cache',
    metadata,
    Column('article_id', Integer, primary_key=True),
    
    # Latest metrics (from article_metrics)
    Column('latest_views', Integer, default=0),
    Column('latest_reactions', Integer, default=0),
    Column('latest_comments', Integer, default=0),
    Column('latest_collected_at', DateTime(timezone=True)),
    
    # Aggregated metrics
    Column('total_view_growth', Integer, default=0, 
           comment='Total views gained since first collection'),
    Column('avg_views_per_day', Float, nullable=True),
    Column('peak_velocity', Float, nullable=True, comment='Highest views/hour recorded'),
    
    # Quality metrics (from quality_analytics.py)
    Column('quality_score', Float, nullable=True, 
           comment='(completion × 0.7) + (min(engagement, 20) × 1.5)'),
    Column('completion_rate', Float, nullable=True, comment='Percentage of article read'),
    Column('engagement_rate', Float, nullable=True, comment='(reactions + comments) / views'),
    
    # Follower attribution (from advanced_analytics.py:118-227)
    Column('attributed_followers_7d', Float, nullable=True, 
           comment='Share-of-voice attribution over 7 days'),
    Column('attributed_followers_30d', Float, nullable=True),
    
    # Cache metadata
    Column('updated_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
    
    comment='''
    Materialized statistics for fast dashboard queries
    Refresh via scheduled job (e.g., hourly)
    Replaces complex aggregation queries
    '''
)

Index('ix_article_stats_quality', article_stats_cache.c.quality_score)
Index('ix_article_stats_updated', article_stats_cache.c.updated_at)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_all_tables():
    """
    Returns all table objects in dependency order (for migrations)
    
    This ordering ensures:
    1. Parent tables created before children
    2. Foreign key constraints valid
    3. Safe for drop operations in reverse order
    """
    return [
        # Core tables (no dependencies)
        snapshots,
        author_themes,
        
        # Article metrics (referenced by many tables)
        article_metrics,
        
        # Follower tracking
        follower_events,
        followers,
        
        # Content tables (depend on article_metrics)
        article_content,
        article_code_blocks,
        article_links,
        
        # Analytics tables (depend on article_metrics)
        daily_analytics,
        referrers,
        article_history,
        milestone_events,
        
        # Comment tables
        comments,
        comment_insights,
        
        # Classification tables
        article_theme_mapping,
        
        # Cache (depends on everything)
        article_stats_cache,
    ]


def get_table(table_name: str) -> Table:
    """Get table object by name"""
    for table in get_all_tables():
        if table.name == table_name:
            return table
    raise ValueError(f"Table '{table_name}' not found")


# ============================================================================
# POSTGRESQL-SPECIFIC PATTERNS FOR BUSINESS LOGIC
# ============================================================================

"""
SQL PATTERNS TO PRESERVE FROM SQLITE:

1. PROXIMITY SEARCH (closest timestamp):
   SQLite:
     ORDER BY ABS(julianday(collected_at) - julianday(?))
   
   PostgreSQL:
     ORDER BY ABS(EXTRACT(EPOCH FROM collected_at) - EXTRACT(EPOCH FROM %s))
     -- OR --
     ORDER BY ABS(collected_at - %s::timestamptz)


2. INCREMENTAL PROCESSING (find unprocessed):
   SELECT c.comment_id, c.body_html 
   FROM comments c
   LEFT JOIN comment_insights i ON c.comment_id = i.comment_id
   WHERE i.comment_id IS NULL
   -- Same in PostgreSQL


3. INSERT OR IGNORE (idempotency):
   SQLite:
     INSERT OR IGNORE INTO comments (comment_id, ...) VALUES (?, ...)
   
   PostgreSQL:
     INSERT INTO comments (comment_id, ...) 
     VALUES (%s, ...)
     ON CONFLICT (comment_id) DO NOTHING


4. INSERT OR REPLACE (upsert):
   SQLite:
     INSERT OR REPLACE INTO daily_analytics (article_id, date, ...) VALUES (?, ?, ...)
   
   PostgreSQL:
     INSERT INTO daily_analytics (article_id, date, ...) 
     VALUES (%s, %s, ...)
     ON CONFLICT (article_id, date) 
     DO UPDATE SET page_views = EXCLUDED.page_views, ...


5. 7-DAY WINDOW WITH 6-HOUR TOLERANCE:
   SQLite:
     WHERE julianday(collected_at) BETWEEN julianday(?) - 0.25 AND julianday(?) + 0.25
   
   PostgreSQL:
     WHERE collected_at BETWEEN %s::timestamptz - INTERVAL '6 hours' 
                            AND %s::timestamptz + INTERVAL '6 hours'


6. QUALITY SCORE CALCULATION:
   -- Same in both
   quality_score = (completion * 0.7) + (LEAST(engagement, 20) * 1.5)


7. SENTIMENT THRESHOLDS:
   CASE 
     WHEN sentiment_score >= 0.3 THEN '🌟 Positif'
     WHEN sentiment_score <= -0.2 THEN '😟 Négatif'
     ELSE '😐 Neutre'
   END AS mood


8. ROW_FACTORY REPLACEMENT:
   SQLite:
     conn.row_factory = sqlite3.Row
     row['column_name']
   
   SQLAlchemy:
     result = conn.execute(query)
     for row in result.mappings():  # Returns dict-like rows
         value = row['column_name']


9. ARRAY AGGREGATION:
   PostgreSQL advantage - native ARRAY support:
     SELECT article_id, ARRAY_AGG(language ORDER BY block_order) as languages
     FROM article_code_blocks
     GROUP BY article_id


10. FULL-TEXT SEARCH (PostgreSQL only):
    -- Add tsvector column to article_content
    ALTER TABLE article_content ADD COLUMN search_vector tsvector;
    UPDATE article_content SET search_vector = 
      to_tsvector('english', coalesce(body_markdown, ''));
    CREATE INDEX ix_article_content_search ON article_content USING GIN(search_vector);
    
    -- Search query
    SELECT * FROM article_content 
    WHERE search_vector @@ to_tsquery('english', 'python & tutorial');
"""


# ============================================================================
# MIGRATION NOTES
# ============================================================================

"""
MIGRATION FROM SQLITE TO POSTGRESQL:

1. Schema Creation:
   from app.db.tables import metadata
   from app.db.connection import get_engine
   
   engine = get_engine()
   metadata.create_all(engine)

2. Data Migration (ETL):
   - Export SQLite to CSV/JSON
   - Transform data types:
     * TEXT tags → JSONB or ARRAY(String)
     * INTEGER timestamps → timestamptz
     * NULL handling
   - Bulk INSERT via COPY or execute_values()

3. Enable pgvector:
   CREATE EXTENSION IF NOT EXISTS vector;

4. Table Partitioning (daily_analytics):
   -- Parent table created by SQLAlchemy
   -- Create partitions for each month:
   CREATE TABLE daily_analytics_2024_01 PARTITION OF daily_analytics
   FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
   
   -- Automate with pg_partman or Python script

5. Performance Tuning:
   -- Analyze tables
   ANALYZE article_metrics;
   ANALYZE comments;
   
   -- Vacuum
   VACUUM ANALYZE;
   
   -- Check index usage
   SELECT schemaname, tablename, indexname, idx_scan
   FROM pg_stat_user_indexes
   ORDER BY idx_scan;

6. Connection Pooling:
   from sqlalchemy.pool import QueuePool
   engine = create_engine(url, poolclass=QueuePool, pool_size=20)

7. Replication Slot (for real-time sync):
   CREATE PUBLICATION devto_pub FOR ALL TABLES;
   -- Subscribe from read replicas
"""
