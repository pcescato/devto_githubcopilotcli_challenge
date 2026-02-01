#!/usr/bin/env python3
"""
Fix Comments Table - Add Missing Unique Constraint
===================================================

The comments table is missing the uq_comments_comment_id constraint
which is referenced in the INSERT...ON CONFLICT statement.

Usage:
    python -m app.fix_comments_constraint
"""

from sqlalchemy import text
from app.db.connection import get_engine


def main():
    """Add missing unique constraint to comments table"""
    print("\n" + "="*70)
    print("🔧 FIXING COMMENTS TABLE CONSTRAINT")
    print("="*70)
    
    engine = get_engine()
    
    with engine.begin() as conn:
        # Check if constraint already exists
        result = conn.execute(text("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_schema = 'devto_analytics' 
            AND table_name = 'comments'
            AND constraint_name = 'uq_comments_comment_id'
        """))
        
        if result.fetchone():
            print("\n✓ Constraint uq_comments_comment_id already exists")
        else:
            print("\n📝 Creating unique constraint on comment_id...")
            
            # Add the constraint
            conn.execute(text("""
                ALTER TABLE devto_analytics.comments
                ADD CONSTRAINT uq_comments_comment_id UNIQUE (comment_id)
            """))
            
            print("✅ Constraint created successfully")
        
        # Show current constraints
        result = conn.execute(text("""
            SELECT constraint_name, constraint_type 
            FROM information_schema.table_constraints 
            WHERE table_schema = 'devto_analytics' 
            AND table_name = 'comments'
            ORDER BY constraint_name
        """))
        
        constraints = result.fetchall()
        
        print("\n📋 Current constraints on comments table:")
        for name, ctype in constraints:
            print(f"  - {name} ({ctype})")
    
    print("\n" + "="*70)
    print("✅ COMMENTS TABLE READY")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
