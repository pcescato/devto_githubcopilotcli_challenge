# DEV.to Analytics - PostgreSQL Schema Requirements

## Installation

```bash
pip install sqlalchemy psycopg2-binary pgvector python-dotenv
```

## Environment Variables

Create `.env` file:

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=devto_analytics
POSTGRES_USER=your_username
POSTGRES_PASSWORD=your_password
```

## Database Setup

### 1. Create PostgreSQL 18 Database

```bash
createdb devto_analytics
```

### 2. Enable Extensions

```bash
psql devto_analytics -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql devto_analytics -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
psql devto_analytics -c "CREATE EXTENSION IF NOT EXISTS btree_gin;"
```

### 3. Initialize Schema

```python
from app.db.connection import init_schema, init_extensions

# Run once
init_extensions()
init_schema()
```

## Usage Examples

### Basic Connection

```python
from app.db.connection import get_connection, get_engine
from app.db.tables import article_metrics
from sqlalchemy import select

# Using context manager (recommended)
with get_connection() as conn:
    stmt = select(article_metrics).where(article_metrics.c.views > 100)
    result = conn.execute(stmt)
    
    for row in result.mappings():  # Dict-like rows (replaces row_factory)
        print(f"{row['title']}: {row['views']} views")
```

### INSERT OR IGNORE Pattern

```python
from app.db.connection import insert_or_ignore, get_connection
from app.db.tables import comments

with get_connection() as conn:
    comment_data = {
        'comment_id': 'abc123',
        'article_id': 12345,
        'author_username': 'jane_dev',
        'body_html': '<p>Great article!</p>',
        'collected_at': datetime.now()
    }
    
    rows_inserted = insert_or_ignore(conn, comments, comment_data)
    print(f"Inserted {rows_inserted} rows")  # 0 if conflict
```

### INSERT OR UPDATE (Upsert)

```python
from app.db.connection import insert_or_update, get_connection
from app.db.tables import daily_analytics
from datetime import datetime

with get_connection() as conn:
    analytics_data = {
        'article_id': 12345,
        'date': datetime.now().date(),
        'page_views': 150,
        'reactions_total': 12,
        'collected_at': datetime.now()
    }
    
    rows_affected = insert_or_update(
        conn,
        daily_analytics,
        analytics_data,
        conflict_cols=['article_id', 'date']
    )
```

### Proximity Search (Find Closest Snapshot)

```python
from app.db.connection import find_closest_snapshot, get_connection
from app.db.tables import follower_events
from datetime import datetime, timedelta

with get_connection() as conn:
    target_time = datetime.now() - timedelta(days=7)
    
    closest = find_closest_snapshot(
        conn,
        follower_events,
        'collected_at',
        target_time,
        tolerance_hours=6
    )
    
    if closest:
        print(f"Follower count at {closest['collected_at']}: {closest['follower_count']}")
```

### Weighted Follower Attribution

```python
from app.db.queries import weighted_follower_attribution
from app.db.connection import get_connection

with get_connection() as conn:
    results = weighted_follower_attribution(conn, hours=168)  # Last 7 days
    
    for item in results:
        print(f"{item['title']}")
        print(f"  Views gained: {item['views_gain']}")
        print(f"  Traffic share: {item['traffic_share']:.1%}")
        print(f"  Attributed followers: {item['attributed_followers']:.1f}")
```

### Quality Score Calculation

```python
from app.db.queries import calculate_quality_scores
from app.db.connection import get_connection

with get_connection() as conn:
    scores = calculate_quality_scores(conn, min_views=20)
    
    for article in scores[:10]:  # Top 10
        print(f"{article['title']}")
        print(f"  Quality Score: {article['quality_score']:.1f}")
        print(f"  Completion: {article['completion_rate']:.1f}%")
        print(f"  Engagement: {article['engagement_rate']:.1f}%")
```

### Sentiment Analysis (Incremental Processing)

```python
from app.db.queries import get_unanalyzed_comments, classify_sentiment
from app.db.connection import get_connection, insert_or_ignore
from app.db.tables import comment_insights
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

vader = SentimentIntensityAnalyzer()

with get_connection() as conn:
    # Get comments that haven't been analyzed yet
    unanalyzed = get_unanalyzed_comments(conn, author_username="your_username")
    
    for comment in unanalyzed:
        # Clean and analyze
        text = comment['body_text']  # Assume HTML already cleaned
        scores = vader.polarity_scores(text)
        sentiment_score = scores['compound']
        mood = classify_sentiment(sentiment_score)
        
        # Store results
        insight_data = {
            'comment_id': comment['comment_id'],
            'sentiment_score': sentiment_score,
            'mood': mood,
            'analyzed_at': datetime.now()
        }
        
        insert_or_ignore(conn, comment_insights, insight_data)
```

### Vector Similarity Search

```python
from app.db.queries import find_similar_articles
from app.db.connection import get_connection

with get_connection() as conn:
    similar = find_similar_articles(conn, article_id=12345, limit=5)
    
    for article in similar:
        print(f"{article['title']}")
        print(f"  Distance: {article['distance']:.4f}")
```

## Table Partitioning (daily_analytics)

### Create Monthly Partitions

```sql
-- Create partition for January 2024
CREATE TABLE devto_analytics.daily_analytics_2024_01 
PARTITION OF devto_analytics.daily_analytics
FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Create partition for February 2024
CREATE TABLE devto_analytics.daily_analytics_2024_02 
PARTITION OF devto_analytics.daily_analytics
FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
```

### Automate with Python

```python
from sqlalchemy import text
from app.db.connection import get_connection
from datetime import datetime
from dateutil.relativedelta import relativedelta

def create_monthly_partition(year: int, month: int):
    """Create partition for specific month"""
    start_date = datetime(year, month, 1)
    end_date = start_date + relativedelta(months=1)
    
    partition_name = f"daily_analytics_{year}_{month:02d}"
    
    sql = f"""
    CREATE TABLE IF NOT EXISTS devto_analytics.{partition_name}
    PARTITION OF devto_analytics.daily_analytics
    FOR VALUES FROM ('{start_date.date()}') TO ('{end_date.date()}');
    """
    
    with get_connection() as conn:
        conn.execute(text(sql))
        print(f"✅ Created partition: {partition_name}")

# Create partitions for next 12 months
start = datetime.now()
for i in range(12):
    date = start + relativedelta(months=i)
    create_monthly_partition(date.year, date.month)
```

## Performance Tuning

### Analyze Tables After Data Load

```python
from sqlalchemy import text
from app.db.connection import get_connection

with get_connection() as conn:
    conn.execute(text("ANALYZE devto_analytics.article_metrics;"))
    conn.execute(text("ANALYZE devto_analytics.comments;"))
    conn.execute(text("ANALYZE devto_analytics.daily_analytics;"))
    print("✅ Statistics updated")
```

### Check Index Usage

```python
from sqlalchemy import text
from app.db.connection import get_connection

with get_connection() as conn:
    result = conn.execute(text("""
        SELECT 
            schemaname,
            tablename,
            indexname,
            idx_scan,
            idx_tup_read,
            idx_tup_fetch
        FROM pg_stat_user_indexes
        WHERE schemaname = 'devto_analytics'
        ORDER BY idx_scan DESC;
    """))
    
    for row in result.mappings():
        print(f"{row['tablename']}.{row['indexname']}: {row['idx_scan']} scans")
```

## Migration from SQLite

### Export SQLite Data

```python
import sqlite3
import json
from datetime import datetime

# Export article_metrics
conn = sqlite3.connect('devto_metrics.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM article_metrics")
rows = cursor.fetchall()

articles = []
for row in rows:
    articles.append({
        'collected_at': row['collected_at'],
        'article_id': row['article_id'],
        'title': row['title'],
        'slug': row['slug'],
        'published_at': row['published_at'],
        'views': row['views'],
        'reactions': row['reactions'],
        'comments': row['comments'],
        'reading_time_minutes': row['reading_time_minutes'],
        'tag_list': json.loads(row['tags']) if row['tags'] else []  # Convert to array
    })

# Save to JSON
with open('article_metrics.json', 'w') as f:
    json.dump(articles, f, indent=2)
```

### Import to PostgreSQL

```python
import json
from app.db.connection import get_connection, insert_or_ignore
from app.db.tables import article_metrics

with open('article_metrics.json') as f:
    articles = json.load(f)

with get_connection() as conn:
    for article in articles:
        insert_or_ignore(conn, article_metrics, article)
    
    print(f"✅ Imported {len(articles)} article snapshots")
```

## Monitoring & Health Checks

```python
from app.db.connection import check_connection

if check_connection():
    print("✅ Database is healthy")
else:
    print("❌ Database connection failed")
```

## Complete Application Setup

```python
#!/usr/bin/env python3
"""
Initialize DEV.to Analytics PostgreSQL Database
"""

from app.db.connection import (
    check_connection,
    init_extensions,
    init_schema
)

def main():
    print("🚀 DEV.to Analytics - Database Setup")
    print("=" * 60)
    
    # 1. Check connection
    print("\n1️⃣ Checking database connection...")
    if not check_connection():
        print("❌ Failed to connect. Check your environment variables.")
        return
    print("✅ Connection successful")
    
    # 2. Initialize extensions
    print("\n2️⃣ Initializing PostgreSQL extensions...")
    try:
        init_extensions()
    except Exception as e:
        print(f"⚠️  Extension initialization failed: {e}")
        print("   Continue anyway (extensions may already exist)")
    
    # 3. Create schema
    print("\n3️⃣ Creating database schema...")
    try:
        init_schema()
    except Exception as e:
        print(f"❌ Schema creation failed: {e}")
        return
    
    print("\n" + "=" * 60)
    print("✅ Database setup complete!")
    print("\nNext steps:")
    print("  1. Run data migration from SQLite (if needed)")
    print("  2. Create monthly partitions for daily_analytics")
    print("  3. Start collecting data with devto_tracker.py")

if __name__ == "__main__":
    main()
```

## Best Practices

1. **Always use context manager** for connections
2. **Use insert_or_ignore** for idempotent operations (comments, followers)
3. **Use insert_or_update** for upserts (daily_analytics, referrers)
4. **Use find_closest_snapshot** for time-series proximity searches
5. **Leverage result.mappings()** for dict-like row access (replaces row_factory)
6. **Create partitions proactively** for daily_analytics (monthly)
7. **Run ANALYZE regularly** after bulk inserts
8. **Monitor index usage** and drop unused indexes
9. **Use article_stats_cache** for dashboard queries (refresh hourly)
10. **Test proximity search tolerance** (6 hours may need adjustment based on collection frequency)
