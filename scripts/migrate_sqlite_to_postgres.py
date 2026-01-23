#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script
Migrates data from devto_metrics.db (SQLite) to PostgreSQL 18

Features:
- Schema-aware migration using app/db/tables.py
- Batch inserts with progress bars
- Data type conversions (tags, dates, arrays)
- ON CONFLICT handling for idempotent operations
- Dependency-aware table ordering
- Comprehensive error handling
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text, inspect
from sqlalchemy.dialects.postgresql import insert
from tqdm import tqdm

# Load environment
load_dotenv()

# Import schema
from app.db.tables import metadata, get_all_tables


# ============================================================================
# CONFIGURATION
# ============================================================================

SQLITE_DB = project_root / "devto_metrics.db"
BATCH_SIZE = 1000

# PostgreSQL connection
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'devto')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'devto_secure_password')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'devto_analytics')

POSTGRES_URI = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


# ============================================================================
# DATA TYPE CONVERSIONS
# ============================================================================

def convert_tags_to_list(tags_value: Any) -> Optional[List[str]]:
    """
    Convert SQLite tags (JSON string or comma-separated) to Python list
    
    SQLite formats:
    - JSON array: '["python", "postgresql"]'
    - Comma-separated: 'python,postgresql'
    - Empty/None
    
    Returns:
        List of tag strings or None
    """
    if not tags_value:
        return None
    
    if isinstance(tags_value, list):
        return tags_value
    
    if isinstance(tags_value, str):
        # Try JSON first
        if tags_value.startswith('['):
            try:
                parsed = json.loads(tags_value)
                return parsed if isinstance(parsed, list) else None
            except json.JSONDecodeError:
                pass
        
        # Try comma-separated
        if ',' in tags_value:
            return [tag.strip() for tag in tags_value.split(',') if tag.strip()]
        
        # Single tag
        return [tags_value.strip()] if tags_value.strip() else None
    
    return None


def convert_to_utc_datetime(date_value: Any) -> Optional[datetime]:
    """
    Convert various date formats to timezone-aware UTC datetime
    
    Handles:
    - ISO 8601 strings: '2024-01-23T12:34:56Z'
    - Unix timestamps: 1706014496
    - datetime objects (naive or aware)
    - None/NULL
    
    Returns:
        Timezone-aware UTC datetime or None
    """
    if not date_value:
        return None
    
    # Already a datetime
    if isinstance(date_value, datetime):
        if date_value.tzinfo is None:
            return date_value.replace(tzinfo=timezone.utc)
        return date_value.astimezone(timezone.utc)
    
    # String (ISO format)
    if isinstance(date_value, str):
        try:
            # Remove 'Z' suffix if present
            date_str = date_value.rstrip('Z')
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, AttributeError):
            return None
    
    # Unix timestamp (int or float)
    if isinstance(date_value, (int, float)):
        try:
            return datetime.fromtimestamp(date_value, tz=timezone.utc)
        except (ValueError, OSError):
            return None
    
    return None


def convert_jsonb(value: Any) -> Optional[Dict]:
    """
    Convert SQLite JSON string to Python dict for JSONB
    
    Returns:
        Python dict or None
    """
    if not value:
        return None
    
    if isinstance(value, dict):
        return value
    
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    
    return None


# ============================================================================
# COLUMN MAPPING
# ============================================================================

# Maps SQLite column names to PostgreSQL column names
COLUMN_MAPPING = {
    'page_views_count': 'views',  # Common rename
    'page_views': 'views',
}

# Columns that need timezone-aware datetime conversion
DATETIME_COLUMNS = {
    'collected_at', 'published_at', 'created_at', 'changed_at', 
    'occurred_at', 'followed_at', 'date', 'classified_at',
    'edited_at_api'  # This is string, handled separately
}

# Columns that need tags → list conversion
TAG_COLUMNS = {'tags', 'tag_list'}

# Columns that need JSON → dict conversion (for JSONB)
JSONB_COLUMNS = {'tags', 'keywords', 'named_entities', 'main_topics'}


# ============================================================================
# DATABASE CONNECTIONS
# ============================================================================

def get_sqlite_connection():
    """Connect to SQLite database"""
    if not SQLITE_DB.exists():
        raise FileNotFoundError(f"SQLite database not found: {SQLITE_DB}")
    
    conn = sqlite3.connect(str(SQLITE_DB))
    conn.row_factory = sqlite3.Row  # Dict-like access
    return conn


def get_postgres_engine():
    """Create PostgreSQL engine"""
    return create_engine(POSTGRES_URI, pool_pre_ping=True)


# ============================================================================
# MIGRATION LOGIC
# ============================================================================

def get_sqlite_table_columns(sqlite_conn, table_name: str) -> List[str]:
    """Get column names from SQLite table"""
    cursor = sqlite_conn.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def transform_row(row: Dict[str, Any], table_name: str, postgres_columns: set) -> Dict[str, Any]:
    """
    Transform SQLite row to PostgreSQL format
    
    Handles:
    - Column name mapping
    - Data type conversions
    - Missing columns
    
    Args:
        row: SQLite row as dict
        table_name: Target table name
        postgres_columns: Set of valid PostgreSQL column names
    
    Returns:
        Transformed row ready for PostgreSQL
    """
    transformed = {}
    
    for sqlite_col, value in row.items():
        # Map column name if needed
        postgres_col = COLUMN_MAPPING.get(sqlite_col, sqlite_col)
        
        # Skip if column doesn't exist in PostgreSQL schema
        if postgres_col not in postgres_columns:
            continue
        
        # Convert NULL/None
        if value is None:
            transformed[postgres_col] = None
            continue
        
        # Convert datetime columns
        if postgres_col in DATETIME_COLUMNS:
            transformed[postgres_col] = convert_to_utc_datetime(value)
        
        # Convert tag_list to array
        elif postgres_col == 'tag_list':
            transformed[postgres_col] = convert_tags_to_list(value)
        
        # Convert tags to JSONB (if separate column)
        elif postgres_col == 'tags' and table_name in ['article_metrics', 'article_content']:
            # For JSONB columns, convert JSON string to dict
            transformed[postgres_col] = convert_jsonb(value)
        
        # Convert other JSONB columns
        elif postgres_col in JSONB_COLUMNS:
            transformed[postgres_col] = convert_jsonb(value)
        
        # Pass through other values
        else:
            transformed[postgres_col] = value
    
    return transformed


def migrate_table(
    sqlite_conn,
    postgres_engine,
    table_name: str,
    postgres_table,
    batch_size: int = BATCH_SIZE
) -> int:
    """
    Migrate data from SQLite table to PostgreSQL table
    
    Features:
    - Batch inserts for performance
    - Progress bar with tqdm
    - ON CONFLICT DO NOTHING for idempotent operations
    - Error handling with detailed logging
    
    Args:
        sqlite_conn: SQLite connection
        postgres_engine: PostgreSQL engine
        table_name: Name of table to migrate
        postgres_table: SQLAlchemy Table object
        batch_size: Number of rows per batch
    
    Returns:
        Number of rows successfully migrated
    """
    print(f"\n📊 Migrating {table_name}...")
    
    # Check if SQLite table exists
    try:
        count_result = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
        total_rows = count_result[0]
    except sqlite3.OperationalError as e:
        print(f"  ⚠️  Table '{table_name}' not found in SQLite: {e}")
        return 0
    
    if total_rows == 0:
        print(f"  ℹ️  Table '{table_name}' is empty")
        return 0
    
    # Get PostgreSQL columns
    postgres_columns = {col.name for col in postgres_table.columns}
    
    # Fetch all rows from SQLite
    cursor = sqlite_conn.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    migrated_count = 0
    error_count = 0
    
    # Process in batches with progress bar
    with tqdm(total=total_rows, desc=f"  {table_name}", unit="rows") as pbar:
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            
            # Transform rows
            transformed_rows = []
            for row in batch:
                try:
                    row_dict = dict(row)
                    transformed = transform_row(row_dict, table_name, postgres_columns)
                    if transformed:  # Skip empty rows
                        transformed_rows.append(transformed)
                except Exception as e:
                    error_count += 1
                    print(f"\n  ⚠️  Error transforming row: {e}")
                    continue
            
            # Insert batch into PostgreSQL
            if transformed_rows:
                try:
                    with postgres_engine.connect() as conn:
                        # Use INSERT ... ON CONFLICT DO NOTHING for idempotency
                        stmt = insert(postgres_table).values(transformed_rows)
                        stmt = stmt.on_conflict_do_nothing()
                        result = conn.execute(stmt)
                        conn.commit()
                        migrated_count += result.rowcount
                
                except Exception as e:
                    error_count += len(transformed_rows)
                    print(f"\n  ❌ Error inserting batch: {e}")
                    # Try inserting rows one by one to identify problematic row
                    for row_data in transformed_rows:
                        try:
                            with postgres_engine.connect() as conn:
                                stmt = insert(postgres_table).values(row_data)
                                stmt = stmt.on_conflict_do_nothing()
                                result = conn.execute(stmt)
                                conn.commit()
                                if result.rowcount > 0:
                                    migrated_count += 1
                                    error_count -= 1
                        except Exception as row_error:
                            print(f"\n  ⚠️  Failed row: {row_error}")
                            print(f"      Data: {row_data}")
            
            pbar.update(len(batch))
    
    # Summary
    print(f"  ✅ Migrated: {migrated_count}/{total_rows} rows", end="")
    if error_count > 0:
        print(f" (⚠️  {error_count} errors)")
    else:
        print()
    
    return migrated_count


# ============================================================================
# MAIN MIGRATION
# ============================================================================

def verify_postgres_schema(engine):
    """Verify PostgreSQL schema exists and has tables"""
    inspector = inspect(engine)
    schemas = inspector.get_schema_names()
    
    if 'devto_analytics' not in schemas:
        raise RuntimeError(
            "Schema 'devto_analytics' not found. "
            "Run 'python app/init_database.py' first."
        )
    
    tables = inspector.get_table_names(schema='devto_analytics')
    if not tables:
        raise RuntimeError(
            "No tables found in 'devto_analytics' schema. "
            "Run 'python app/init_database.py' first."
        )
    
    return tables


def main():
    """Main migration orchestration"""
    print("=" * 70)
    print("🚀 SQLite → PostgreSQL Migration")
    print("=" * 70)
    
    # Check connections
    print("\n1️⃣ Checking connections...")
    
    # SQLite
    try:
        sqlite_conn = get_sqlite_connection()
        print(f"  ✅ SQLite: {SQLITE_DB}")
    except Exception as e:
        print(f"  ❌ SQLite connection failed: {e}")
        return 1
    
    # PostgreSQL
    try:
        postgres_engine = get_postgres_engine()
        with postgres_engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"  ✅ PostgreSQL: Connected")
    except Exception as e:
        print(f"  ❌ PostgreSQL connection failed: {e}")
        print(f"     Check credentials in .env file")
        return 1
    
    # Verify schema
    print("\n2️⃣ Verifying PostgreSQL schema...")
    try:
        postgres_tables = verify_postgres_schema(postgres_engine)
        print(f"  ✅ Found {len(postgres_tables)} tables in devto_analytics schema")
    except Exception as e:
        print(f"  ❌ {e}")
        return 1
    
    # Get migration order (respects dependencies)
    print("\n3️⃣ Planning migration order...")
    tables_to_migrate = get_all_tables()
    print(f"  ✅ Will migrate {len(tables_to_migrate)} tables in dependency order")
    
    # Show order
    print("\n📋 Migration order:")
    for i, table in enumerate(tables_to_migrate, 1):
        print(f"  {i:2d}. {table.name}")
    
    # Confirm
    print("\n⚠️  This will migrate data from SQLite to PostgreSQL.")
    print("    Existing data in PostgreSQL will be preserved (ON CONFLICT DO NOTHING).")
    response = input("\n   Continue? [y/N]: ").strip().lower()
    if response != 'y':
        print("\n❌ Migration cancelled")
        return 0
    
    # Migrate each table
    print("\n4️⃣ Migrating data...")
    print("=" * 70)
    
    total_migrated = 0
    successful_tables = 0
    failed_tables = []
    
    for table in tables_to_migrate:
        try:
            count = migrate_table(
                sqlite_conn,
                postgres_engine,
                table.name,
                table,
                BATCH_SIZE
            )
            total_migrated += count
            if count > 0:
                successful_tables += 1
        except Exception as e:
            print(f"\n  ❌ Failed to migrate {table.name}: {e}")
            failed_tables.append(table.name)
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ Migration Complete!")
    print("=" * 70)
    print(f"\n📊 Summary:")
    print(f"  • Total rows migrated: {total_migrated:,}")
    print(f"  • Successful tables: {successful_tables}/{len(tables_to_migrate)}")
    
    if failed_tables:
        print(f"\n⚠️  Failed tables ({len(failed_tables)}):")
        for table_name in failed_tables:
            print(f"    - {table_name}")
    
    # Verification
    print("\n🔍 Verification:")
    print("  Run these commands to verify:")
    print(f"    psql {POSTGRES_DB} -c \"SELECT COUNT(*) FROM devto_analytics.article_metrics;\"")
    print(f"    psql {POSTGRES_DB} -c \"SELECT COUNT(*) FROM devto_analytics.comments;\"")
    
    # Close connections
    sqlite_conn.close()
    postgres_engine.dispose()
    
    return 0 if not failed_tables else 1


if __name__ == "__main__":
    sys.exit(main())
