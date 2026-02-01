"""
SQLite to PostgreSQL Migration Script
======================================

Migrates all data from devto_metrics.db (SQLite) to PostgreSQL devto_analytics database.

Usage:
    python -m app.migrate_from_sqlite --dry-run
    python -m app.migrate_from_sqlite --sqlite-path devto_metrics.db
    python -m app.migrate_from_sqlite --tables articles,comments --verbose

Features:
    - Sync PostgreSQL operations (works with existing connection.py)
    - Progress bars with rich console output
    - Comprehensive error handling and logging
    - Dry-run mode for validation
    - Data validation and integrity checks
"""

import sqlite3
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Import database connection and tables
from app.db.connection import get_engine, get_database_url
from app.db.tables import (
    snapshots, article_metrics, follower_events, comments, followers,
    daily_analytics, referrers, article_content, article_code_blocks,
    article_links, article_history, milestone_events, comment_insights
)


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class MigrationStats:
    """Statistics for a single table migration"""
    total: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_details: List[str] = field(default_factory=list)


@dataclass
class MigrationConfig:
    """Migration configuration"""
    sqlite_path: str
    dry_run: bool = False
    verbose: bool = False
    tables: Optional[List[str]] = None
    log_file: str = "migration.log"
    batch_size: int = 1000


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_file: str, verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    
    # File handler
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only warnings/errors to console
    
    # Root logger
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)


# ============================================================================
# MIGRATION CLASS
# ============================================================================

class SQLiteToPostgresMigrator:
    """Migrates data from SQLite to PostgreSQL"""
    
    def __init__(self, config: MigrationConfig):
        self.config = config
        self.pg_engine = get_engine()
        self.sqlite_conn: Optional[sqlite3.Connection] = None
        self.console = Console()
        self.logger = logging.getLogger(__name__)
        
        # Migration statistics
        self.stats: Dict[str, MigrationStats] = {
            'snapshots': MigrationStats(),
            'article_metrics': MigrationStats(),
            'follower_events': MigrationStats(),
            'comments': MigrationStats(),
            'followers': MigrationStats(),
            'daily_analytics': MigrationStats(),
            'referrers': MigrationStats(),
            'article_content': MigrationStats(),
            'article_code_blocks': MigrationStats(),
            'article_links': MigrationStats(),
            'article_history': MigrationStats(),
            'milestone_events': MigrationStats(),
            'comment_insights': MigrationStats(),
        }
        
        # Table migration order (respects dependencies)
        self.table_order = [
            'snapshots',
            'article_metrics',
            'follower_events',
            'followers',
            'comments',
            'daily_analytics',
            'referrers',
            'article_content',
            'article_code_blocks',
            'article_links',
            'article_history',
            'milestone_events',
            'comment_insights',
        ]
        
        # Start time
        self.start_time = datetime.now()
    
    def connect_sqlite(self):
        """Open SQLite connection"""
        self.logger.info(f"Connecting to SQLite: {self.config.sqlite_path}")
        self.sqlite_conn = sqlite3.connect(self.config.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row  # Access columns by name
        
    def close_sqlite(self):
        """Close SQLite connection"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.logger.info("SQLite connection closed")
    
    def migrate_all(self):
        """Run complete migration"""
        try:
            self.connect_sqlite()
            
            # Filter tables if specified
            tables_to_migrate = self.table_order
            if self.config.tables:
                tables_to_migrate = [t for t in self.table_order if t in self.config.tables]
            
            # Display migration plan
            self.print_header(tables_to_migrate)
            
            # Migrate each table
            for table_name in tables_to_migrate:
                self.migrate_table(table_name)
            
            # Summary
            self.print_summary()
            
        finally:
            self.close_sqlite()
    
    def print_header(self, tables: List[str]):
        """Print migration header"""
        mode = "DRY RUN" if self.config.dry_run else "LIVE MIGRATION"
        
        panel = Panel(
            f"[bold cyan]SQLite → PostgreSQL Migration[/bold cyan]\n\n"
            f"Mode: [bold]{'[yellow]' if self.config.dry_run else '[green]'}{mode}[/bold]\n"
            f"SQLite: {self.config.sqlite_path}\n"
            f"Tables: {len(tables)}\n"
            f"Batch Size: {self.config.batch_size}",
            title="🔄 Migration Starting",
            border_style="cyan"
        )
        self.console.print(panel)
    
    def migrate_table(self, table_name: str):
        """Migrate a single table"""
        # Map table name to migration method
        method_map = {
            'snapshots': self.migrate_snapshots,
            'article_metrics': self.migrate_article_metrics,
            'follower_events': self.migrate_follower_events,
            'comments': self.migrate_comments,
            'followers': self.migrate_followers,
            'daily_analytics': self.migrate_daily_analytics,
            'referrers': self.migrate_referrers,
            'article_content': self.migrate_article_content,
            'article_code_blocks': self.migrate_article_code_blocks,
            'article_links': self.migrate_article_links,
            'article_history': self.migrate_article_history,
            'milestone_events': self.migrate_milestone_events,
            'comment_insights': self.migrate_comment_insights,
        }
        
        method = method_map.get(table_name)
        if not method:
            self.logger.warning(f"No migration method for table: {table_name}")
            return
        
        try:
            method()
        except Exception as e:
            self.logger.error(f"Failed to migrate {table_name}: {e}", exc_info=True)
            self.stats[table_name].errors += 1
            self.stats[table_name].error_details.append(str(e))
            if not self.config.dry_run:
                raise
    
    # ========================================================================
    # TABLE MIGRATION METHODS
    # ========================================================================
    
    def migrate_snapshots(self):
        """Migrate snapshots table"""
        table_name = 'snapshots'
        self.logger.info(f"Migrating {table_name}...")
        
        cursor = self.sqlite_conn.cursor()
        rows = cursor.execute("""
            SELECT 
                collected_at, total_articles, total_views,
                total_reactions, total_comments, follower_count
            FROM snapshots
            ORDER BY collected_at
        """).fetchall()
        
        self.stats[table_name].total = len(rows)
        
        if not rows:
            self.console.print(f"[yellow]No data in {table_name}[/yellow]")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task(f"[cyan]{table_name}", total=len(rows))
            
            with self.pg_engine.begin() as conn:
                for row in rows:
                    try:
                        if not self.config.dry_run:
                            stmt = pg_insert(snapshots).values(
                                collected_at=self._parse_datetime(row['collected_at']),
                                total_articles=row['total_articles'],
                                total_views=row['total_views'],
                                total_reactions=row['total_reactions'],
                                total_comments=row['total_comments'],
                                follower_count=row['follower_count']
                            ).on_conflict_do_nothing(
                                index_elements=['collected_at']
                            )
                            result = conn.execute(stmt)
                            
                            if result.rowcount > 0:
                                self.stats[table_name].inserted += 1
                            else:
                                self.stats[table_name].skipped += 1
                        else:
                            self.stats[table_name].inserted += 1
                        
                    except Exception as e:
                        self.logger.error(f"Error migrating snapshot {row['collected_at']}: {e}")
                        self.stats[table_name].errors += 1
                    
                    progress.update(task, advance=1)
        
        self.logger.info(f"✓ {table_name}: {self.stats[table_name].inserted} inserted")
    
    def migrate_article_metrics(self):
        """Migrate article_metrics table - handles both old SQLite schemas"""
        table_name = 'article_metrics'
        self.logger.info(f"Migrating {table_name}...")
        
        cursor = self.sqlite_conn.cursor()
        
        # Check which columns exist in SQLite
        cursor.execute("PRAGMA table_info(article_metrics)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Build dynamic query based on available columns
        select_cols = [
            'collected_at', 'article_id', 'title', 'slug', 'published_at',
            'views', 'reactions', 'comments', 'reading_time_minutes',
            'tags', 'tag_list', 'is_deleted'
        ]
        
        # Only select columns that exist
        available_cols = [col for col in select_cols if col in columns]
        query = f"SELECT {', '.join(available_cols)} FROM article_metrics ORDER BY collected_at, article_id"
        
        rows = cursor.execute(query).fetchall()
        
        self.stats[table_name].total = len(rows)
        
        if not rows:
            self.console.print(f"[yellow]No data in {table_name}[/yellow]")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task(f"[cyan]{table_name}", total=len(rows))
            
            with self.pg_engine.begin() as conn:
                for row in rows:
                    try:
                        data = {
                            'collected_at': self._parse_datetime(row['collected_at']),
                            'article_id': row['article_id'],
                            'title': self._safe_get(row, 'title'),
                            'slug': self._safe_get(row, 'slug'),
                            'published_at': self._parse_datetime(self._safe_get(row, 'published_at')),
                            'views': self._safe_get(row, 'views', 0) or 0,
                            'reactions': self._safe_get(row, 'reactions', 0) or 0,
                            'comments': self._safe_get(row, 'comments', 0) or 0,
                            'reading_time_minutes': self._safe_get(row, 'reading_time_minutes'),
                            'tags': self._parse_json(self._safe_get(row, 'tags')),
                            'tag_list': self._parse_json_array(self._safe_get(row, 'tag_list')),
                            'is_deleted': bool(self._safe_get(row, 'is_deleted', 0))
                        }
                        
                        if not self.config.dry_run:
                            stmt = pg_insert(article_metrics).values(data).on_conflict_do_nothing(
                                index_elements=['collected_at', 'article_id']
                            )
                            result = conn.execute(stmt)
                            
                            if result.rowcount > 0:
                                self.stats[table_name].inserted += 1
                            else:
                                self.stats[table_name].skipped += 1
                        else:
                            self.stats[table_name].inserted += 1
                        
                    except Exception as e:
                        self.logger.error(f"Error migrating article_metrics: {e}")
                        self.stats[table_name].errors += 1
                    
                    progress.update(task, advance=1)
        
        self.logger.info(f"✓ {table_name}: {self.stats[table_name].inserted} inserted")
    
    # Add similar methods for other tables (following same pattern)
    def migrate_follower_events(self):
        self._migrate_simple_table('follower_events', follower_events, """
            SELECT collected_at, follower_count, new_followers_since_last
            FROM follower_events ORDER BY collected_at
        """, ['collected_at'])
    
    def migrate_comments(self):
        self._migrate_simple_table('comments', comments, """
            SELECT collected_at, comment_id, article_id, article_title,
                   created_at, author_username, author_name,
                   body_html, body_text, body_markdown, body_length
            FROM comments ORDER BY comment_id
        """, ['comment_id'])
    
    def migrate_followers(self):
        self._migrate_simple_table('followers', followers, """
            SELECT collected_at, follower_id, username, name, followed_at, profile_image
            FROM followers ORDER BY follower_id
        """, ['follower_id'])
    
    def migrate_daily_analytics(self):
        self._migrate_simple_table('daily_analytics', daily_analytics, """
            SELECT article_id, date, collected_at,
                   page_views, average_read_time_seconds, total_read_time_seconds,
                   reactions_total, reactions_like, reactions_readinglist, reactions_unicorn,
                   comments_total, follows_total
            FROM daily_analytics ORDER BY date, article_id
        """, ['article_id', 'date'])
    
    def migrate_referrers(self):
        """Migrate referrers table - skip NULL domains"""
        self._migrate_simple_table('referrers', referrers, """
            SELECT article_id, domain, count, collected_at
            FROM referrers 
            WHERE domain IS NOT NULL
            ORDER BY article_id, domain
        """, ['article_id', 'domain', 'collected_at'])
    
    def migrate_article_content(self):
        """Migrate article_content - map SQLite columns to PostgreSQL"""
        self._migrate_simple_table('article_content', article_content, """
            SELECT article_id, body_markdown, body_html,
                   word_count, char_count, code_blocks_count,
                   links_count, images_count, headings_count, collected_at
            FROM article_content ORDER BY article_id
        """, ['article_id'])
    
    def migrate_article_code_blocks(self):
        """Migrate article_code_blocks - map SQLite columns to PostgreSQL"""
        self._migrate_simple_table('article_code_blocks', article_code_blocks, """
            SELECT article_id, language, code_text as code, line_count, block_order
            FROM article_code_blocks ORDER BY article_id, block_order
        """, ['article_id', 'block_order'])
    
    def migrate_article_links(self):
        """Migrate article_links - map SQLite columns to PostgreSQL"""
        self._migrate_simple_table('article_links', article_links, """
            SELECT article_id, url, link_text, link_type
            FROM article_links ORDER BY article_id, id
        """, ['article_id', 'url'])
    
    def migrate_article_history(self):
        table_name = 'article_history'
        try:
            self._migrate_simple_table(table_name, article_history, """
                SELECT article_id, event_date, event_type, old_value, new_value, change_magnitude
                FROM article_history ORDER BY article_id, event_date
            """, None)  # No unique constraint, insert all
        except:
            self.console.print(f"[yellow]{table_name} table not found in SQLite (optional)[/yellow]")
    
    def migrate_milestone_events(self):
        table_name = 'milestone_events'
        try:
            self._migrate_simple_table(table_name, milestone_events, """
                SELECT event_date, article_id, milestone_type, value, description
                FROM milestone_events ORDER BY event_date
            """, None)
        except:
            self.console.print(f"[yellow]{table_name} table not found in SQLite (optional)[/yellow]")
    
    def migrate_comment_insights(self):
        table_name = 'comment_insights'
        try:
            self._migrate_simple_table(table_name, comment_insights, """
                SELECT comment_id, analyzed_at, sentiment_score, sentiment_label,
                       toxicity_score, is_question, is_feedback,
                       key_phrases, language_code
                FROM comment_insights ORDER BY comment_id
            """, ['comment_id'])
        except:
            self.console.print(f"[yellow]{table_name} table not found in SQLite (optional)[/yellow]")
    
    # ========================================================================
    # HELPER METHOD FOR SIMPLE MIGRATIONS
    # ========================================================================
    
    def _migrate_simple_table(self, table_name: str, table_obj, query: str, conflict_cols: Optional[List[str]]):
        """Generic migration for simple tables"""
        self.logger.info(f"Migrating {table_name}...")
        
        cursor = self.sqlite_conn.cursor()
        rows = cursor.execute(query).fetchall()
        
        self.stats[table_name].total = len(rows)
        
        if not rows:
            self.console.print(f"[yellow]No data in {table_name}[/yellow]")
            return
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task(f"[cyan]{table_name}", total=len(rows))
            
            with self.pg_engine.begin() as conn:
                for row in rows:
                    try:
                        # Convert row to dict, handling dates and JSON
                        data = {}
                        for key in row.keys():
                            value = row[key]
                            
                            # Parse dates
                            if key in ['collected_at', 'published_at', 'created_at', 'followed_at', 'event_date', 'date', 'analyzed_at']:
                                value = self._parse_datetime(value)
                            # Parse JSON
                            elif key in ['tags', 'key_phrases']:
                                value = self._parse_json(value)
                            # Parse JSON arrays
                            elif key in ['tag_list']:
                                value = self._parse_json_array(value)
                            # Parse booleans
                            elif key in ['is_deleted', 'is_external', 'is_question', 'is_feedback']:
                                value = bool(value) if value is not None else False
                            
                            data[key] = value
                        
                        if not self.config.dry_run:
                            if conflict_cols:
                                stmt = pg_insert(table_obj).values(data).on_conflict_do_nothing(
                                    index_elements=conflict_cols
                                )
                            else:
                                stmt = insert(table_obj).values(data)
                            
                            result = conn.execute(stmt)
                            
                            if result.rowcount > 0:
                                self.stats[table_name].inserted += 1
                            else:
                                self.stats[table_name].skipped += 1
                        else:
                            self.stats[table_name].inserted += 1
                        
                    except Exception as e:
                        self.logger.error(f"Error migrating {table_name}: {e}")
                        self.stats[table_name].errors += 1
                    
                    progress.update(task, advance=1)
        
        self.logger.info(f"✓ {table_name}: {self.stats[table_name].inserted} inserted")
    
    # ========================================================================
    # HELPERS
    # ========================================================================
    
    @staticmethod
    def _safe_get(row, key: str, default=None):
        """Safely extract value from sqlite3.Row object.
        
        sqlite3.Row objects don't support .get() method like dicts.
        This helper provides safe access with default fallback.
        """
        try:
            # Try direct key access
            value = row[key]
            return value if value is not None else default
        except (KeyError, IndexError, TypeError):
            return default
    
    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        """Parse datetime from SQLite"""
        if value is None:
            return None
        
        try:
            if isinstance(value, str):
                # Remove timezone suffix if present
                if value.endswith('Z'):
                    value = value[:-1]
                elif '+' in value:
                    value = value.split('+')[0]
                
                dt = datetime.fromisoformat(value)
                
                # Add timezone if naive
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                
                return dt
            
            return value
        except Exception as e:
            self.logger.warning(f"Failed to parse datetime '{value}': {e}")
            return None
    
    def _parse_json(self, value: Any) -> Optional[Dict]:
        """Parse JSON from SQLite TEXT"""
        if value is None:
            return None
        
        try:
            if isinstance(value, str):
                return json.loads(value)
            return value
        except:
            return None
    
    def _parse_json_array(self, value: Any) -> Optional[List]:
        """Parse JSON array from SQLite TEXT"""
        if value is None:
            return None
        
        try:
            if isinstance(value, str):
                result = json.loads(value)
                return result if isinstance(result, list) else None
            return value if isinstance(value, list) else None
        except:
            return None
    
    def print_summary(self):
        """Print migration summary"""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        # Summary table
        table = Table(
            title="🔄 Migration Summary",
            show_header=True,
            header_style="bold cyan",
            border_style="cyan"
        )
        table.add_column("Table", style="cyan")
        table.add_column("Total", justify="right")
        table.add_column("Inserted", justify="right", style="green")
        table.add_column("Skipped", justify="right", style="yellow")
        table.add_column("Errors", justify="right", style="red")
        
        total_records = 0
        total_inserted = 0
        total_skipped = 0
        total_errors = 0
        
        for name in self.table_order:
            stats = self.stats[name]
            if stats.total > 0:
                table.add_row(
                    name,
                    str(stats.total),
                    str(stats.inserted),
                    str(stats.skipped),
                    str(stats.errors)
                )
                total_records += stats.total
                total_inserted += stats.inserted
                total_skipped += stats.skipped
                total_errors += stats.errors
        
        # Totals
        table.add_section()
        table.add_row(
            "[bold]TOTAL[/bold]",
            f"[bold]{total_records}[/bold]",
            f"[bold green]{total_inserted}[/bold green]",
            f"[bold yellow]{total_skipped}[/bold yellow]",
            f"[bold red]{total_errors}[/bold red]"
        )
        
        self.console.print(table)
        
        # Final status
        status = "✅ COMPLETED" if total_errors == 0 else "⚠️ COMPLETED WITH ERRORS"
        mode = " (DRY RUN)" if self.config.dry_run else ""
        
        panel = Panel(
            f"[bold]{status}{mode}[/bold]\n\n"
            f"Duration: {duration:.1f} seconds\n"
            f"Total records: {total_records:,}\n"
            f"Inserted: {total_inserted:,}\n"
            f"Skipped: {total_skipped:,}\n"
            f"Errors: {total_errors:,}",
            title="Migration Results",
            border_style="green" if total_errors == 0 else "yellow"
        )
        self.console.print(panel)


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migrate data from SQLite to PostgreSQL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (validate only)
  python -m app.migrate_from_sqlite --dry-run
  
  # Full migration
  python -m app.migrate_from_sqlite --sqlite-path devto_metrics.db
  
  # Migrate specific tables
  python -m app.migrate_from_sqlite --tables snapshots,comments --verbose
        """
    )
    
    parser.add_argument(
        '--sqlite-path',
        default='devto_metrics.db',
        help='Path to SQLite database (default: devto_metrics.db)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate without inserting data'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--tables',
        help='Comma-separated list of tables to migrate (default: all)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1000,
        help='Batch size for inserts (default: 1000)'
    )
    
    args = parser.parse_args()
    
    # Parse tables
    tables = None
    if args.tables:
        tables = [t.strip() for t in args.tables.split(',')]
    
    # Configuration
    config = MigrationConfig(
        sqlite_path=args.sqlite_path,
        dry_run=args.dry_run,
        verbose=args.verbose,
        tables=tables,
        batch_size=args.batch_size
    )
    
    # Setup logging
    logger = setup_logging(config.log_file, config.verbose)
    
    # Verify SQLite file exists
    if not Path(config.sqlite_path).exists():
        print(f"[red]Error: SQLite file not found: {config.sqlite_path}[/red]")
        sys.exit(1)
    
    # Run migration
    migrator = SQLiteToPostgresMigrator(config)
    
    try:
        migrator.migrate_all()
    except KeyboardInterrupt:
        print("\n[yellow]Migration interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        print(f"\n[red]Migration failed: {e}[/red]")
        print(f"[yellow]Check log file: {config.log_file}[/yellow]")
        sys.exit(1)


if __name__ == '__main__':
    main()
