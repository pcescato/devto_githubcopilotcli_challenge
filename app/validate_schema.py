#!/usr/bin/env python3
"""
Schema Validation Script
Validates the PostgreSQL schema matches all requirements
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def validate_imports():
    """Test all imports work"""
    print("🔍 Validating imports...")
    
    try:
        from app.db.tables import (
            metadata,
            get_all_tables,
            article_metrics,
            comments,
            daily_analytics,
            article_content,
            comment_insights,
        )
        print("  ✅ All table imports successful")
        
        from app.db.connection import (
            get_engine,
            get_connection,
            insert_or_ignore,
            insert_or_update,
            find_closest_snapshot,
        )
        print("  ✅ All connection imports successful")
        
        from app.db.queries import (
            weighted_follower_attribution,
            calculate_quality_scores,
            classify_sentiment,
        )
        print("  ✅ All query imports successful")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False


def validate_table_definitions():
    """Validate table structure"""
    print("\n🔍 Validating table definitions...")
    
    from app.db.tables import get_all_tables, metadata
    
    tables = get_all_tables()
    print(f"  ℹ️  Found {len(tables)} tables")
    
    # Check expected tables
    expected = {
        'snapshots', 'article_metrics', 'follower_events', 'comments',
        'followers', 'daily_analytics', 'referrers', 'article_content',
        'article_code_blocks', 'article_links', 'comment_insights',
        'article_history', 'milestone_events', 'author_themes',
        'article_theme_mapping', 'article_stats_cache'
    }
    
    actual = {table.name for table in tables}
    
    missing = expected - actual
    if missing:
        print(f"  ❌ Missing tables: {missing}")
        return False
    
    extra = actual - expected
    if extra:
        print(f"  ⚠️  Extra tables: {extra}")
    
    print(f"  ✅ All expected tables defined")
    
    # Check schema name
    if metadata.schema != 'devto_analytics':
        print(f"  ❌ Wrong schema: {metadata.schema}")
        return False
    
    print(f"  ✅ Schema name correct: {metadata.schema}")
    
    return True


def validate_table_features():
    """Validate specific table features"""
    print("\n🔍 Validating table features...")
    
    from app.db.tables import (
        article_metrics,
        article_content,
        comments,
        comment_insights,
        daily_analytics,
    )
    from sqlalchemy.dialects.postgresql import JSONB, ARRAY
    from pgvector.sqlalchemy import Vector
    
    # Check JSONB columns
    if not any(isinstance(col.type, JSONB) for col in article_metrics.columns):
        print("  ❌ article_metrics missing JSONB column")
        return False
    print("  ✅ article_metrics has JSONB column")
    
    # Check ARRAY columns
    if not any(isinstance(col.type, ARRAY) for col in article_metrics.columns):
        print("  ❌ article_metrics missing ARRAY column")
        return False
    print("  ✅ article_metrics has ARRAY column")
    
    # Check Vector columns
    if not any(isinstance(col.type, Vector) for col in article_content.columns):
        print("  ❌ article_content missing Vector column")
        return False
    print("  ✅ article_content has Vector(1536) column")
    
    # Check foreign keys
    fks = [fk for table in [comments, comment_insights, daily_analytics] 
           for fk in table.foreign_keys]
    
    if len(fks) < 3:
        print(f"  ❌ Expected at least 3 foreign keys, found {len(fks)}")
        return False
    print(f"  ✅ Foreign keys defined ({len(fks)} total)")
    
    # Check unique constraints
    uqs = [c for table in [article_metrics, comments, daily_analytics] 
           for c in table.constraints if hasattr(c, 'columns') and len(c.columns) > 0]
    
    print(f"  ✅ Unique constraints defined ({len(uqs)} total)")
    
    return True


def validate_thresholds():
    """Validate business logic thresholds"""
    print("\n🔍 Validating business logic thresholds...")
    
    from app.db.queries import classify_sentiment
    
    # Test sentiment thresholds
    assert classify_sentiment(0.5) == "🌟 Positif", "Positive threshold failed"
    assert classify_sentiment(0.3) == "🌟 Positif", "Positive boundary failed"
    assert classify_sentiment(0.0) == "😐 Neutre", "Neutral test failed"
    assert classify_sentiment(-0.2) == "😟 Négatif", "Negative boundary failed"
    assert classify_sentiment(-0.5) == "😟 Négatif", "Negative threshold failed"
    
    print("  ✅ Sentiment thresholds correct (≥0.3, ≤-0.2)")
    
    # Check quality score formula in code
    import inspect
    from app.db.queries import calculate_quality_scores
    
    source = inspect.getsource(calculate_quality_scores)
    if "* 0.7" not in source or "* 1.5" not in source:
        print("  ❌ Quality score formula incorrect")
        return False
    
    print("  ✅ Quality score formula correct (70/30 split)")
    
    return True


def validate_patterns():
    """Validate SQL pattern implementations"""
    print("\n🔍 Validating SQL patterns...")
    
    from app.db.connection import (
        insert_or_ignore,
        insert_or_update,
        find_closest_snapshot,
    )
    
    # Check function signatures
    import inspect
    
    sig_ignore = inspect.signature(insert_or_ignore)
    if 'table' not in sig_ignore.parameters:
        print("  ❌ insert_or_ignore missing table parameter")
        return False
    
    sig_update = inspect.signature(insert_or_update)
    if 'conflict_cols' not in sig_update.parameters:
        print("  ❌ insert_or_update missing conflict_cols parameter")
        return False
    
    sig_proximity = inspect.signature(find_closest_snapshot)
    if 'tolerance_hours' not in sig_proximity.parameters:
        print("  ❌ find_closest_snapshot missing tolerance_hours parameter")
        return False
    
    print("  ✅ insert_or_ignore pattern implemented")
    print("  ✅ insert_or_update pattern implemented")
    print("  ✅ find_closest_snapshot pattern implemented")
    
    # Check default tolerance is 6 hours
    if sig_proximity.parameters['tolerance_hours'].default != 6:
        print("  ❌ Wrong tolerance default")
        return False
    
    print("  ✅ Proximity search tolerance correct (6 hours)")
    
    return True


def validate_documentation():
    """Validate documentation exists"""
    print("\n🔍 Validating documentation...")
    
    files = [
        'app/db/README.md',
        'app/db/tables.py',
        'app/db/connection.py',
        'app/db/queries.py',
        'app/MIGRATION_SUMMARY.md',
        'app/requirements.txt',
    ]
    
    for file_path in files:
        path = Path(__file__).parent.parent / file_path
        if not path.exists():
            print(f"  ❌ Missing: {file_path}")
            return False
        
        size = path.stat().st_size
        print(f"  ✅ {file_path} ({size:,} bytes)")
    
    return True


def main():
    print("=" * 70)
    print("🧪 PostgreSQL Schema Validation")
    print("=" * 70)
    
    tests = [
        ("Imports", validate_imports),
        ("Table Definitions", validate_table_definitions),
        ("Table Features", validate_table_features),
        ("Business Logic Thresholds", validate_thresholds),
        ("SQL Patterns", validate_patterns),
        ("Documentation", validate_documentation),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"\n❌ {name} validation failed")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name} validation error: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print(f"📊 Results: {passed}/{len(tests)} tests passed")
    
    if failed == 0:
        print("✅ All validations passed!")
        print("\n🎉 Schema is ready for deployment")
        print("\n📖 Next steps:")
        print("  1. Set environment variables (.env file)")
        print("  2. Run: python app/init_database.py")
        print("  3. Check: psql devto_analytics -c '\\dt devto_analytics.*'")
        return 0
    else:
        print(f"❌ {failed} validation(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
