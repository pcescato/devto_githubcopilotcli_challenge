"""
Database Connection Management
PostgreSQL 18 with connection pooling and health checks
"""

from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import os


def get_database_url() -> str:
    """
    Construct PostgreSQL connection URL from environment variables
    
    Required environment variables:
        POSTGRES_HOST (default: localhost)
        POSTGRES_PORT (default: 5432)
        POSTGRES_DB (default: devto_analytics)
        POSTGRES_USER (required)
        POSTGRES_PASSWORD (required)
    """
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    database = os.getenv('POSTGRES_DB', 'devto_analytics')
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD')
    
    if not user or not password:
        raise ValueError(
            "Missing required environment variables: POSTGRES_USER and POSTGRES_PASSWORD"
        )
    
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def get_engine(
    pool_size: int = 20,
    max_overflow: int = 10,
    pool_timeout: int = 30,
    echo: bool = False
) -> Engine:
    """
    Create SQLAlchemy engine with connection pooling
    
    Args:
        pool_size: Number of connections to maintain in pool (default: 20)
        max_overflow: Max connections beyond pool_size (default: 10)
        pool_timeout: Seconds to wait for connection (default: 30)
        echo: Log all SQL statements (default: False)
    
    Returns:
        SQLAlchemy Engine with QueuePool
    
    Pattern replaces: sqlite3.connect() with conn.row_factory = sqlite3.Row
    Use: result.mappings() to get dict-like rows
    """
    url = get_database_url()
    
    engine = create_engine(
        url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_pre_ping=True,  # Verify connections before use
        echo=echo,
        future=True,  # Use SQLAlchemy 2.0 style
    )
    
    return engine


@contextmanager
def get_connection(engine: Optional[Engine] = None):
    """
    Context manager for database connections (replaces SQLite pattern)
    
    SQLite pattern:
        conn = self.db.get_connection()
        try:
            # ... operations ...
            conn.commit()
        finally:
            conn.close()
    
    PostgreSQL pattern:
        with get_connection() as conn:
            # ... operations ...
            # Auto-commit on success, rollback on exception
    
    Usage:
        with get_connection() as conn:
            result = conn.execute(text("SELECT * FROM articles"))
            for row in result.mappings():
                print(row['title'])  # Dict-like access (replaces row_factory)
    """
    if engine is None:
        engine = get_engine()
    
    conn = engine.connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_connection() -> bool:
    """
    Health check: Verify database connectivity
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def init_extensions():
    """
    Initialize required PostgreSQL extensions
    
    Must be run by superuser or user with CREATE EXTENSION privilege
    """
    engine = get_engine()
    with engine.connect() as conn:
        # pgvector for embeddings
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # pg_trgm for fuzzy text search
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        
        # btree_gin for composite indexes
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gin"))
        
        conn.commit()
    
    print("✅ PostgreSQL extensions initialized")


def init_schema():
    """
    Create all tables (replaces _run_migrations() from SQLite)
    
    SQLite pattern:
        def _run_migrations(self):
            conn = self.get_connection()
            try:
                cursor.execute("SELECT column FROM table LIMIT 1")
            except:
                cursor.execute("ALTER TABLE table ADD COLUMN column TYPE")
    
    PostgreSQL pattern:
        metadata.create_all(engine)  # Idempotent - uses IF NOT EXISTS
    """
    from .tables import metadata
    
    engine = get_engine()
    
    # Create schema if not exists
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS devto_analytics"))
        conn.commit()
    
    # Create all tables
    metadata.create_all(engine)
    
    print("✅ Database schema initialized")


# ============================================================================
# INSERT PATTERNS (preserve SQLite business logic)
# ============================================================================

def insert_or_ignore(conn, table, values_dict: dict):
    """
    PostgreSQL equivalent of SQLite's INSERT OR IGNORE
    
    SQLite:
        INSERT OR IGNORE INTO comments (comment_id, ...) VALUES (?, ...)
    
    PostgreSQL:
        INSERT INTO comments (comment_id, ...) VALUES (...) ON CONFLICT DO NOTHING
    
    Returns:
        Number of rows inserted (0 if conflict)
    """
    from sqlalchemy import insert
    
    stmt = insert(table).values(**values_dict).on_conflict_do_nothing()
    result = conn.execute(stmt)
    return result.rowcount


def insert_or_update(conn, table, values_dict: dict, conflict_cols: list):
    """
    PostgreSQL equivalent of SQLite's INSERT OR REPLACE
    
    SQLite:
        INSERT OR REPLACE INTO daily_analytics (article_id, date, ...) VALUES (?, ?, ...)
    
    PostgreSQL:
        INSERT INTO daily_analytics (article_id, date, ...) 
        VALUES (...)
        ON CONFLICT (article_id, date) 
        DO UPDATE SET page_views = EXCLUDED.page_views, ...
    
    Args:
        conn: SQLAlchemy connection
        table: Table object
        values_dict: Column → value mapping
        conflict_cols: List of column names that define uniqueness
    
    Returns:
        Number of rows affected
    """
    from sqlalchemy import insert
    
    stmt = insert(table).values(**values_dict)
    
    # Build update dict (all columns except conflict columns)
    update_dict = {
        col: stmt.excluded[col]
        for col in values_dict.keys()
        if col not in conflict_cols
    }
    
    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_cols,
        set_=update_dict
    )
    
    result = conn.execute(stmt)
    return result.rowcount


# ============================================================================
# PROXIMITY SEARCH PATTERN
# ============================================================================

def find_closest_snapshot(conn, table, timestamp_col: str, target_time, 
                          tolerance_hours: int = 6, additional_filters=None):
    """
    Find row with timestamp closest to target (preserves SQLite pattern)
    
    SQLite pattern (advanced_analytics.py:134-143):
        SELECT follower_count FROM follower_events 
        ORDER BY ABS(strftime('%s', collected_at) - strftime('%s', ?)) ASC 
        LIMIT 1
    
    PostgreSQL pattern:
        SELECT * FROM follower_events 
        WHERE collected_at BETWEEN target - INTERVAL '6 hours' 
                               AND target + INTERVAL '6 hours'
        ORDER BY ABS(EXTRACT(EPOCH FROM collected_at) - EXTRACT(EPOCH FROM target))
        LIMIT 1
    
    Args:
        conn: SQLAlchemy connection
        table: Table object
        timestamp_col: Column name to search on
        target_time: datetime to find closest match for
        tolerance_hours: Max hours difference (default: 6)
        additional_filters: List of WHERE clause conditions
    
    Returns:
        Row mapping (dict-like) or None
    """
    from sqlalchemy import select, func, and_
    from datetime import timedelta
    
    col = getattr(table.c, timestamp_col)
    
    # Tolerance window
    start = target_time - timedelta(hours=tolerance_hours)
    end = target_time + timedelta(hours=tolerance_hours)
    
    # Build query
    filters = [col.between(start, end)]
    if additional_filters:
        filters.extend(additional_filters)
    
    # Proximity calculation
    epoch_target = func.extract('epoch', target_time)
    epoch_col = func.extract('epoch', col)
    distance = func.abs(epoch_col - epoch_target)
    
    stmt = (
        select(table)
        .where(and_(*filters))
        .order_by(distance)
        .limit(1)
    )
    
    result = conn.execute(stmt)
    row = result.mappings().first()
    
    return row


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Check connection
    if check_connection():
        print("✅ Database connection successful")
    
    # Initialize extensions and schema
    try:
        init_extensions()
        init_schema()
        print("✅ Database ready")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
