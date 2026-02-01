#!/bin/bash
################################################################################
# Quick Migration Script - SQLite to PostgreSQL
# Usage: ./migrate.sh [dry-run|migrate|verify]
################################################################################

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQLITE_DB="${SQLITE_DB:-devto_metrics.db}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check if running in Docker or host
if [ -f "/.dockerenv" ]; then
    # Inside container
    PYTHON_CMD="python -m app.migrate_from_sqlite"
else
    # On host - use docker exec
    PYTHON_CMD="docker exec -it devto_fastapi python -m app.migrate_from_sqlite"
fi

case "${1:-help}" in
    dry-run)
        log_info "Running migration dry-run (no changes)..."
        $PYTHON_CMD --dry-run --verbose --sqlite-path "$SQLITE_DB"
        ;;
    
    migrate)
        log_info "Running full migration..."
        log_warn "This will insert data into PostgreSQL!"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            $PYTHON_CMD --sqlite-path "$SQLITE_DB" --verbose
            log_info "Migration completed!"
            echo ""
            log_info "Next steps:"
            echo "  1. Run: ./migrate.sh verify"
            echo "  2. Check services: docker compose ps"
            echo "  3. Test API: curl http://localhost:8000/api/articles/quality-scores"
        else
            log_info "Migration cancelled."
        fi
        ;;
    
    verify)
        log_info "Verifying migration..."
        docker exec -it devto_fastapi python << 'PYEOF'
import asyncio
from sqlalchemy import select, func
from app.db.connection import get_async_engine
from app.db.tables import (
    snapshots, article_metrics, follower_events, comments,
    followers, daily_analytics, referrers, article_content
)

async def verify():
    engine = get_async_engine()
    async with engine.begin() as conn:
        print("\nPostgreSQL Record Counts:")
        print("─" * 40)
        
        tables = [
            ('snapshots', snapshots),
            ('article_metrics', article_metrics),
            ('follower_events', follower_events),
            ('comments', comments),
            ('followers', followers),
            ('daily_analytics', daily_analytics),
            ('referrers', referrers),
            ('article_content', article_content),
        ]
        
        total = 0
        for name, table in tables:
            result = await conn.execute(select(func.count()).select_from(table))
            count = result.scalar()
            total += count
            print(f"{name:20} {count:>8,} rows")
        
        print("─" * 40)
        print(f"{'TOTAL':20} {total:>8,} rows")
        print()

asyncio.run(verify())
PYEOF
        ;;
    
    resume)
        log_info "Resuming migration from checkpoint..."
        $PYTHON_CMD --resume --verbose --sqlite-path "$SQLITE_DB"
        ;;
    
    tables)
        if [ -z "${2:-}" ]; then
            log_error "Usage: ./migrate.sh tables <table1,table2,...>"
            exit 1
        fi
        log_info "Migrating specific tables: $2"
        $PYTHON_CMD --tables "$2" --verbose --sqlite-path "$SQLITE_DB"
        ;;
    
    status)
        log_info "Checking migration status..."
        
        # Check for checkpoint
        if [ -f "migration_checkpoint.json" ]; then
            log_info "Found checkpoint file:"
            cat migration_checkpoint.json | jq '.'
        else
            log_info "No checkpoint found - migration not started or completed"
        fi
        
        # Check log file
        if [ -f "migration.log" ]; then
            echo ""
            log_info "Last 10 log entries:"
            tail -10 migration.log
        fi
        ;;
    
    clean)
        log_info "Cleaning up migration files..."
        rm -f migration.log migration_checkpoint.json
        log_info "Cleaned: migration.log, migration_checkpoint.json"
        ;;
    
    help|*)
        cat << 'HELP'
╔════════════════════════════════════════════════════════════════╗
║          SQLite to PostgreSQL Migration Helper                 ║
╚════════════════════════════════════════════════════════════════╝

Usage: ./migrate.sh <command>

Commands:
  dry-run      Run migration without making changes (recommended first)
  migrate      Run full migration (will prompt for confirmation)
  verify       Check record counts in PostgreSQL
  resume       Resume interrupted migration from checkpoint
  tables       Migrate specific tables only
               Example: ./migrate.sh tables "snapshots,comments"
  status       Show current migration status and logs
  clean        Remove migration log and checkpoint files
  help         Show this help message

Examples:
  # Test migration first
  ./migrate.sh dry-run
  
  # Run full migration
  ./migrate.sh migrate
  
  # Verify results
  ./migrate.sh verify
  
  # Resume if interrupted
  ./migrate.sh resume
  
  # Migrate specific tables
  ./migrate.sh tables "daily_analytics,referrers"

Environment Variables:
  SQLITE_DB    Path to SQLite database (default: devto_metrics.db)

Files Created:
  migration.log              Detailed migration log
  migration_checkpoint.json  Resume checkpoint (if interrupted)

For detailed documentation, see: MIGRATION_GUIDE.md
HELP
        ;;
esac
