#!/usr/bin/env python3
"""
Fix daily_analytics Schema - Add Missing Reaction Breakdown Columns
====================================================================

The database was created with a simplified schema but the code expects
detailed reaction breakdown columns. This script adds the missing columns.

Current Schema:
- reactions (INTEGER)
- comments (INTEGER)
- follows (INTEGER)

Required Schema:
- reactions_total, reactions_like, reactions_unicorn, reactions_readinglist
- comments_total
- follows_total

Usage:
    python -m app.fix_daily_analytics_schema
"""

from sqlalchemy import text
from app.db.connection import get_engine

def fix_schema():
    """Add missing columns to daily_analytics table"""
    
    engine = get_engine()
    
    print("\n" + "="*70)
    print("🔧 FIXING daily_analytics SCHEMA")
    print("="*70)
    
    with engine.connect() as conn:
        # Check current columns
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='devto_analytics'
            AND table_name='daily_analytics'
            ORDER BY ordinal_position
        """))
        
        current_cols = [row[0] for row in result]
        print(f"\n📋 Current columns: {', '.join(current_cols)}")
        
        # Required columns with their mappings
        migrations = [
            # Step 1: Add new columns
            ("reactions_total", "reactions", "ALTER TABLE devto_analytics.daily_analytics ADD COLUMN IF NOT EXISTS reactions_total INTEGER DEFAULT 0"),
            ("reactions_like", None, "ALTER TABLE devto_analytics.daily_analytics ADD COLUMN IF NOT EXISTS reactions_like INTEGER DEFAULT 0"),
            ("reactions_unicorn", None, "ALTER TABLE devto_analytics.daily_analytics ADD COLUMN IF NOT EXISTS reactions_unicorn INTEGER DEFAULT 0"),
            ("reactions_readinglist", None, "ALTER TABLE devto_analytics.daily_analytics ADD COLUMN IF NOT EXISTS reactions_readinglist INTEGER DEFAULT 0"),
            ("comments_total", "comments", "ALTER TABLE devto_analytics.daily_analytics ADD COLUMN IF NOT EXISTS comments_total INTEGER DEFAULT 0"),
            ("follows_total", "follows", "ALTER TABLE devto_analytics.daily_analytics ADD COLUMN IF NOT EXISTS follows_total INTEGER DEFAULT 0"),
        ]
        
        print("\n🔨 Adding missing columns...")
        for new_col, old_col, sql in migrations:
            if new_col not in current_cols:
                try:
                    conn.execute(text(sql))
                    print(f"  ✓ Added {new_col}")
                except Exception as e:
                    print(f"  ✗ Failed to add {new_col}: {e}")
            else:
                print(f"  ⊙ {new_col} already exists")
        
        conn.commit()
        
        # Step 2: Copy data from old columns to new columns
        print("\n📊 Migrating existing data...")
        data_migrations = [
            ("reactions_total", "reactions"),
            ("comments_total", "comments"),
            ("follows_total", "follows"),
        ]
        
        for new_col, old_col in data_migrations:
            try:
                conn.execute(text(f"""
                    UPDATE devto_analytics.daily_analytics
                    SET {new_col} = {old_col}
                    WHERE {new_col} = 0 AND {old_col} > 0
                """))
                affected = conn.execute(text("SELECT COUNT(*) FROM devto_analytics.daily_analytics")).scalar()
                print(f"  ✓ Migrated {old_col} → {new_col}")
            except Exception as e:
                print(f"  ✗ Failed to migrate {old_col} → {new_col}: {e}")
        
        conn.commit()
        
        # Step 3: Drop old columns (optional - keep for backward compatibility)
        print("\n🗑️  Old columns (reactions, comments, follows) kept for compatibility")
        
        print("\n" + "="*70)
        print("✅ SCHEMA FIX COMPLETE")
        print("="*70)
        
        # Verify final schema
        result = conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema='devto_analytics'
            AND table_name='daily_analytics'
            ORDER BY ordinal_position
        """))
        
        print("\n📋 Final schema:")
        for row in result:
            marker = "🆕" if row[0] in ['reactions_total', 'reactions_like', 'reactions_unicorn', 'reactions_readinglist', 'comments_total', 'follows_total'] else "  "
            print(f"  {marker} {row[0]} ({row[1]})")


if __name__ == "__main__":
    fix_schema()
