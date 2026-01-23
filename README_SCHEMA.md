# DEV.to Analytics - PostgreSQL 18 Schema Migration

## 📦 Deliverables

All work completed. The PostgreSQL 18 schema is **production-ready**.

### 1. Technical Documentation (Phase 1)
- **TECHNICAL_DOCUMENTATION.md** (57 KB, 2,218 lines)
  - Architecture analysis with Mermaid diagrams
  - Complete SQLite schema (13 tables)
  - Data flows and sequences
  - All 10 modules/classes documented
  - 7 key algorithms with code examples
  - Business logic thresholds to preserve

### 2. PostgreSQL Schema (Phase 2)
All files in `app/` directory:

| File | Size | Purpose |
|------|------|---------|
| **db/tables.py** | 26 KB | 18 SQLAlchemy Core Table definitions |
| **db/connection.py** | 9.5 KB | Connection pooling + patterns |
| **db/queries.py** | 16 KB | Business logic functions |
| **db/README.md** | 11 KB | Complete usage guide |
| **init_database.py** | 6.5 KB | Database setup script |
| **validate_schema.py** | 8.6 KB | Schema validation |
| **MIGRATION_SUMMARY.md** | 10 KB | Migration overview |
| **INSTALL.md** | 3 KB | Installation steps |
| **requirements.txt** | 371 B | Dependencies |

## ✅ Requirements Met

### Core Requirements
- ✅ SQLAlchemy Core (Table + MetaData), NOT ORM
- ✅ JSONB for tags, keywords, main_topics
- ✅ ARRAY(String) for tag_list
- ✅ Vector(1536) from pgvector for embeddings
- ✅ Monthly partitioning for daily_analytics
- ✅ All indexes (B-tree for dates, GiST for vectors)
- ✅ Foreign keys with CASCADE
- ✅ Result.mappings() for row_factory behavior

### Business Logic Preserved
- ✅ Proximity search (6-hour tolerance)
- ✅ Incremental processing (LEFT JOIN ... IS NULL)
- ✅ INSERT OR IGNORE for idempotence
- ✅ Follower attribution 7-day window
- ✅ Quality score: (completion × 0.7) + (min(engagement, 20) × 1.5)
- ✅ Sentiment: ≥0.3 positive, ≤-0.2 negative

## 🚀 Quick Start

### Installation
\`\`\`bash
# 1. Install dependencies
cd app
pip install -r requirements.txt

# 2. Configure database (create .env file)
cat > .env << 'END'
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=devto_analytics
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
END

# 3. Initialize database
python3 init_database.py

# 4. Verify (optional)
python3 validate_schema.py
\`\`\`

### Basic Usage
\`\`\`python
from app.db.connection import get_connection
from app.db.tables import article_metrics
from sqlalchemy import select

# Query with dict-like access (row_factory equivalent)
with get_connection() as conn:
    stmt = select(article_metrics).limit(10)
    result = conn.execute(stmt)
    
    for row in result.mappings():  # Like sqlite3.Row
        print(row['article_id'], row['views'])
\`\`\`

## 📊 Schema Overview

### 18 Tables in devto_analytics schema

**Core Tables:**
- `snapshots` - Article snapshots at collection time
- `article_metrics` - Time-series metrics (views, reactions, comments)
- `follower_events` - New follower events with attribution
- `comments` - Comment data with sentiment
- `followers` - Current follower list

**Analytics Tables:**
- `daily_analytics` - Daily stats (partitioned by month)
- `referrers` - Traffic sources

**Content Tables:**
- `article_content` - Full markdown + metadata
- `article_code_blocks` - Extracted code snippets
- `article_links` - Extracted links

**Analysis Tables:**
- `comment_insights` - Engagement analysis
- `article_history` - Significant changes
- `milestone_events` - Achievement tracking

**Intelligence Tables:**
- `author_themes` - DNA analysis themes
- `article_theme_mapping` - Theme assignments
- `article_stats_cache` - Performance cache

**Additional:**
- `tag_evolution` - Tag changes
- `quality_scores` - Article quality ratings

## 🔑 Key Features

### PostgreSQL 18 Enhancements
- **JSONB**: Flexible metadata (tags, keywords, entities) with native indexing
- **ARRAY**: Native list storage (tag_list, topics, phrases)
- **Vector(1536)**: Semantic similarity with cosine distance (`<=>`)
- **Partitioning**: Monthly partitions for time-series data
- **GiST indexes**: Vector similarity search
- **CASCADE**: Proper referential integrity

### Pattern Translations (SQLite → PostgreSQL)

| Pattern | SQLite | PostgreSQL |
|---------|--------|------------|
| Proximity | `ABS(julianday(...))` | `ABS(EXTRACT(EPOCH FROM ...))` |
| 6hr tolerance | `julianday(?) - 0.25` | `%s::timestamptz - INTERVAL '6 hours'` |
| Insert ignore | `INSERT OR IGNORE` | `ON CONFLICT DO NOTHING` |
| Insert replace | `INSERT OR REPLACE` | `ON CONFLICT DO UPDATE SET` |
| Row factory | `conn.row_factory = sqlite3.Row` | `result.mappings()` |

## 📖 Documentation

### Usage Examples (app/db/README.md)
- Connection management
- All SQL patterns (insert_or_ignore, proximity search)
- Business logic functions
- Query optimization tips

### Algorithm Implementations (app/db/queries.py)
1. **weighted_follower_attribution()** - Share of Voice calculation
2. **calculate_quality_scores()** - 70/30 engagement formula
3. **classify_sentiment()** - Threshold-based classification
4. **find_similar_articles()** - pgvector cosine similarity
5. **calculate_velocity()** - Views/hour before/after events
6. **detect_article_restarts()** - 50% growth detection
7. **find_unanswered_questions()** - Engagement opportunities

### Migration Guide (app/MIGRATION_SUMMARY.md)
- Side-by-side comparison
- Data migration scripts
- Validation steps

## 🧪 Validation

Run comprehensive validation:
\`\`\`bash
python3 app/validate_schema.py
\`\`\`

Tests:
- ✅ Imports (SQLAlchemy, pgvector)
- ✅ Table definitions (18 tables)
- ✅ Features (JSONB, ARRAY, Vector, partitioning)
- ✅ Business logic thresholds
- ✅ SQL patterns
- ✅ Documentation completeness

## 📁 Project Structure

\`\`\`
devto_githubcopilotcli_challenge/
├── TECHNICAL_DOCUMENTATION.md    # Phase 1: Analysis
├── README_SCHEMA.md              # This file
│
├── app/                          # Phase 2: PostgreSQL schema
│   ├── db/
│   │   ├── __init__.py
│   │   ├── tables.py             # ⭐ 18 Table definitions
│   │   ├── connection.py         # Connection + patterns
│   │   ├── queries.py            # Business logic
│   │   └── README.md             # Usage guide
│   │
│   ├── init_database.py          # Setup script
│   ├── validate_schema.py        # Validation
│   ├── MIGRATION_SUMMARY.md      # Migration guide
│   ├── INSTALL.md                # Installation steps
│   └── requirements.txt          # Dependencies
│
└── [existing Python files]       # Original SQLite codebase
    ├── devto_tracker.py
    ├── content_collector.py
    ├── nlp_analyzer.py
    ├── advanced_analytics.py
    ├── quality_analytics.py
    ├── dashboard.py
    └── comment_analyzer.py
\`\`\`

## 🎯 Critical Business Logic

### Follower Attribution (7-day window)
\`\`\`python
# Share of Voice algorithm
# Articles within 7 days (168 hours) compete for attribution
# Views within 6 hours of follower event don't count
weight = views_after_6hrs / total_views_all_articles
\`\`\`

### Quality Score Formula
\`\`\`python
# 70% completion, 30% engagement
score = (completion_ratio * 0.7) + (min(engagement_score, 20) * 1.5)
\`\`\`

### Sentiment Classification
\`\`\`python
# Stricter than VADER defaults (-0.05 to 0.05)
if compound >= 0.3:  positive
elif compound <= -0.2: negative
else: neutral
\`\`\`

### Article Restart Detection
\`\`\`python
# 50% growth threshold, 50-view minimum
if current_views >= 50 and growth_rate >= 0.5:
    restart_detected = True
\`\`\`

## 🔧 Configuration

### Environment Variables (.env)
\`\`\`bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=devto_analytics
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
\`\`\`

### Connection Pool (app/db/connection.py)
- QueuePool: 20 connections, 10 overflow
- pool_pre_ping: Health checks enabled
- Context manager: Automatic commit/rollback

## 🐛 Known Limitations

1. **Partitioning**: Requires manual DDL (SQLAlchemy Core limitation)
2. **pgvector**: Needs CREATE EXTENSION (superuser privileges)
3. **Daily analytics**: Limited to 90 days (DEV.to API constraint)
4. **Gap analysis**: Lifetime != sum(increments) due to unlikes

## 📚 References

- SQLAlchemy 2.0 Core: https://docs.sqlalchemy.org/en/20/core/
- pgvector: https://github.com/pgvector/pgvector
- PostgreSQL 18: https://www.postgresql.org/docs/18/
- DEV.to API: https://developers.forem.com/api/v1

## 🎉 Status

**✅ COMPLETE - Production Ready**

All requirements met. Schema validated. Documentation comprehensive.

For support, review:
1. **app/INSTALL.md** - Installation steps
2. **app/db/README.md** - Usage examples
3. **app/MIGRATION_SUMMARY.md** - Migration details
4. **TECHNICAL_DOCUMENTATION.md** - Original analysis

---

**Generated**: 2024
**Schema Version**: PostgreSQL 18
**SQLAlchemy**: Core (NOT ORM)
**Status**: Production Ready ✅
