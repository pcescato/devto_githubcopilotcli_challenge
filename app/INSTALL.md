# PostgreSQL 18 Schema - Installation Guide

## Prerequisites

- Python 3.10+
- PostgreSQL 18
- pip

## Step-by-Step Installation

### 1. Install Python Dependencies

\`\`\`bash
cd app
pip install -r requirements.txt
\`\`\`

Required packages:
- sqlalchemy>=2.0.0
- psycopg2-binary>=2.9.9
- pgvector>=0.2.4
- python-dotenv>=1.0.0

### 2. Create PostgreSQL Database

\`\`\`bash
# Create database
createdb devto_analytics

# Or with psql
psql -c "CREATE DATABASE devto_analytics;"
\`\`\`

### 3. Configure Environment

Create \`.env\` file in project root:

\`\`\`bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=devto_analytics
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
\`\`\`

### 4. Run Validation (Optional)

\`\`\`bash
python3 app/validate_schema.py
\`\`\`

Should show:
- ✅ All 6 validations passed
- ✅ 18 tables defined
- ✅ All patterns implemented

### 5. Initialize Database

\`\`\`bash
python3 app/init_database.py
\`\`\`

This will:
1. Check connection
2. Enable extensions (vector, pg_trgm, btree_gin)
3. Create schema (devto_analytics)
4. Create all 18 tables
5. Create 12 monthly partitions
6. Seed author themes

### 6. Verify Installation

\`\`\`bash
# Check tables
psql devto_analytics -c "\\dt devto_analytics.*"

# Check schema
psql devto_analytics -c "\\d devto_analytics.article_metrics"
\`\`\`

## Quick Test

\`\`\`python
from app.db.connection import check_connection, get_connection
from app.db.tables import article_metrics
from sqlalchemy import select

# Test connection
if check_connection():
    print("✅ Database ready!")

# Test query
with get_connection() as conn:
    stmt = select(article_metrics).limit(1)
    result = conn.execute(stmt)
    print(f"✅ Query successful: {result.rowcount} rows")
\`\`\`

## Troubleshooting

### "No module named 'sqlalchemy'"
\`\`\`bash
pip install -r app/requirements.txt
\`\`\`

### "Connection refused"
Check PostgreSQL is running:
\`\`\`bash
sudo systemctl status postgresql
sudo systemctl start postgresql
\`\`\`

### "Extension vector not found"
Install pgvector:
\`\`\`bash
# Ubuntu/Debian
sudo apt install postgresql-18-pgvector

# Or compile from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
\`\`\`

### "Permission denied for schema"
Grant permissions:
\`\`\`sql
GRANT ALL ON SCHEMA devto_analytics TO your_username;
GRANT ALL ON ALL TABLES IN SCHEMA devto_analytics TO your_username;
\`\`\`

## Next Steps

1. Review **app/db/README.md** for usage examples
2. Migrate data from SQLite (see Migration section)
3. Start collecting: \`python devto_tracker.py --collect\`
4. Run analytics: \`python advanced_analytics.py\`

## Support

- Documentation: app/db/README.md
- Schema details: app/db/tables.py
- Examples: app/db/queries.py
- Summary: app/MIGRATION_SUMMARY.md
