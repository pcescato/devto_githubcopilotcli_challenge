#!/usr/bin/env python3
"""
Database Initialization Script
Sets up PostgreSQL 18 schema for DEV.to Analytics
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.connection import (
    check_connection,
    init_extensions,
    init_schema,
    get_connection
)
from sqlalchemy import text


def create_monthly_partitions(months: int = 12):
    """Create monthly partitions for daily_analytics"""
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    print(f"\n📅 Creating {months} monthly partitions...")
    
    with get_connection() as conn:
        start = datetime.now()
        created = 0
        
        for i in range(months):
            date = start + relativedelta(months=i)
            partition_name = f"daily_analytics_{date.year}_{date.month:02d}"
            start_date = datetime(date.year, date.month, 1)
            end_date = start_date + relativedelta(months=1)
            
            sql = f"""
            CREATE TABLE IF NOT EXISTS devto_analytics.{partition_name}
            PARTITION OF devto_analytics.daily_analytics
            FOR VALUES FROM ('{start_date.date()}') TO ('{end_date.date()}');
            """
            
            try:
                conn.execute(text(sql))
                created += 1
                print(f"  ✓ {partition_name}")
            except Exception as e:
                print(f"  ⚠️  {partition_name}: {e}")
        
        print(f"\n✅ Created {created}/{months} partitions")


def seed_author_themes():
    """Seed default author themes for DNA analysis"""
    from app.db.tables import author_themes
    from app.db.connection import insert_or_ignore
    
    print("\n🧬 Seeding author themes...")
    
    themes = [
        {
            'theme_name': 'Expertise Tech',
            'keywords': ['sql', 'database', 'python', 'cloud', 'docker', 'vps', 'astro', 'hugo', 'vector', 'cte'],
            'description': 'Technical expertise and hands-on tutorials'
        },
        {
            'theme_name': 'Human & Career',
            'keywords': ['cv', 'career', 'feedback', 'developer', 'learning', 'growth'],
            'description': 'Career development and soft skills'
        },
        {
            'theme_name': 'Culture & Agile',
            'keywords': ['agile', 'scrum', 'performance', 'theater', 'laziness', 'management'],
            'description': 'Team culture and agile methodologies'
        }
    ]
    
    with get_connection() as conn:
        for theme in themes:
            try:
                insert_or_ignore(conn, author_themes, theme)
                print(f"  ✓ {theme['theme_name']}")
            except Exception as e:
                print(f"  ⚠️  {theme['theme_name']}: {e}")


def verify_schema():
    """Verify all tables were created successfully"""
    from app.db.tables import get_all_tables
    
    print("\n🔍 Verifying schema...")
    
    with get_connection() as conn:
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'devto_analytics'
            ORDER BY table_name;
        """))
        
        existing_tables = {row[0] for row in result}
        expected_tables = {table.name for table in get_all_tables()}
        
        missing = expected_tables - existing_tables
        extra = existing_tables - expected_tables
        
        if missing:
            print(f"  ⚠️  Missing tables: {', '.join(missing)}")
        
        if extra:
            print(f"  ℹ️  Extra tables (partitions?): {', '.join(extra)}")
        
        print(f"\n  ✅ {len(existing_tables)} tables found")
        print(f"  📊 Expected: {len(expected_tables)}")


def main():
    print("=" * 70)
    print("🚀 DEV.to Analytics - PostgreSQL 18 Database Setup")
    print("=" * 70)
    
    # Check environment variables
    print("\n📋 Checking environment variables...")
    required_vars = ['POSTGRES_USER', 'POSTGRES_PASSWORD']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("\nCreate a .env file with:")
        print("  POSTGRES_HOST=localhost")
        print("  POSTGRES_PORT=5432")
        print("  POSTGRES_DB=devto_analytics")
        print("  POSTGRES_USER=your_username")
        print("  POSTGRES_PASSWORD=your_password")
        return 1
    
    print("  ✅ Environment variables set")
    
    # 1. Check connection
    print("\n1️⃣ Testing database connection...")
    if not check_connection():
        print("❌ Failed to connect to PostgreSQL")
        print("\nTroubleshooting:")
        print("  1. Is PostgreSQL 18 running?")
        print("  2. Are credentials correct?")
        print("  3. Does database exist? (createdb devto_analytics)")
        return 1
    print("  ✅ Connection successful")
    
    # 2. Initialize extensions
    print("\n2️⃣ Initializing PostgreSQL extensions...")
    try:
        init_extensions()
    except Exception as e:
        print(f"  ⚠️  Warning: {e}")
        print("  Extensions may require superuser privileges")
        print("  Run manually: psql devto_analytics -c 'CREATE EXTENSION vector;'")
    
    # 3. Create schema
    print("\n3️⃣ Creating database schema...")
    try:
        init_schema()
    except Exception as e:
        print(f"❌ Schema creation failed: {e}")
        return 1
    
    # 4. Verify schema
    verify_schema()
    
    # 5. Create partitions
    try:
        create_monthly_partitions(months=12)
    except Exception as e:
        print(f"  ⚠️  Partition creation failed: {e}")
        print("  You can create partitions manually later")
    
    # 6. Seed themes
    try:
        seed_author_themes()
    except Exception as e:
        print(f"  ⚠️  Theme seeding failed: {e}")
    
    # Success!
    print("\n" + "=" * 70)
    print("✅ Database setup complete!")
    print("=" * 70)
    print("\n📖 Next steps:")
    print("  1. Review schema: psql devto_analytics -c '\\dt devto_analytics.*'")
    print("  2. Check tables: python -c 'from app.db.tables import get_all_tables; print([t.name for t in get_all_tables()])'")
    print("  3. Migrate data from SQLite (see app/db/README.md)")
    print("  4. Start collecting: python devto_tracker.py --collect")
    print("\n📚 Documentation: app/db/README.md")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
