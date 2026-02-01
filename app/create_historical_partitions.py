#!/usr/bin/env python3
"""
Create Missing Partitions for daily_analytics Table
====================================================

The daily_analytics table is partitioned by date (RANGE), but only 2026
partitions were created during initialization. Historical data from DEV.to
API goes back to 2025, so we need to create those partitions.

Usage:
    python -m app.create_historical_partitions
"""

from sqlalchemy import text
from app.db.connection import get_engine
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def create_partitions_for_year(conn, year: int):
    """Create 12 monthly partitions for a given year"""
    created = 0
    
    for month in range(1, 13):
        partition_name = f"daily_analytics_{year}_{month:02d}"
        start_date = datetime(year, month, 1)
        end_date = start_date + relativedelta(months=1)
        
        sql = f"""
        CREATE TABLE IF NOT EXISTS devto_analytics.{partition_name}
        PARTITION OF devto_analytics.daily_analytics
        FOR VALUES FROM ('{start_date.date()}') TO ('{end_date.date()}');
        """
        
        try:
            conn.execute(text(sql))
            print(f"  ✓ Created {partition_name}")
            created += 1
        except Exception as e:
            if "already exists" in str(e):
                print(f"  ⊙ {partition_name} already exists")
            else:
                print(f"  ✗ Failed to create {partition_name}: {e}")
    
    return created


def main():
    """Create historical partitions for 2025 and future years"""
    print("\n" + "="*70)
    print("🗓️  CREATING HISTORICAL PARTITIONS")
    print("="*70)
    
    engine = get_engine()
    
    with engine.begin() as conn:
        # Check existing partitions
        result = conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'devto_analytics' 
            AND tablename LIKE 'daily_analytics_%'
            ORDER BY tablename
        """))
        
        existing = [row[0] for row in result]
        print(f"\n📋 Existing partitions: {len(existing)}")
        
        # Create 2025 partitions (historical data)
        print("\n📅 Creating 2025 partitions...")
        created_2025 = create_partitions_for_year(conn, 2025)
        
        # Create 2027 partitions (future data)
        print("\n📅 Creating 2027 partitions...")
        created_2027 = create_partitions_for_year(conn, 2027)
        
        # Verify
        result = conn.execute(text("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'devto_analytics' 
            AND tablename LIKE 'daily_analytics_%'
            ORDER BY tablename
        """))
        
        all_partitions = [row[0] for row in result]
        
        print("\n" + "="*70)
        print(f"✅ PARTITIONS CREATED")
        print("="*70)
        print(f"  2025 partitions: {created_2025}")
        print(f"  2027 partitions: {created_2027}")
        print(f"  Total partitions: {len(all_partitions)}")
        print("="*70)
        
        # Show coverage
        print("\n📊 Partition Coverage:")
        for partition in all_partitions:
            print(f"  - {partition}")
    
    print("\n✅ Historical partitions ready for data import!\n")


if __name__ == "__main__":
    main()
