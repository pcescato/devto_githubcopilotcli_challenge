# Table Partitioning - Implementation Note

## Daily Analytics Partitioning

The `daily_analytics` table is partitioned by RANGE on the `date` column for optimal time-series performance.

### Why Manual DDL?

SQLAlchemy Core doesn't support declarative table partitioning. The table is created manually in `app/db/connection.py:init_schema()` using raw DDL:

```sql
CREATE TABLE devto_analytics.daily_analytics (
    ...columns...
) PARTITION BY RANGE (date);
```

### Partition Management

Monthly partitions are created automatically by `init_database.py`:

```python
CREATE TABLE devto_analytics.daily_analytics_2026_01
PARTITION OF devto_analytics.daily_analytics
FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

### Benefits

1. **Query Performance**: Partition pruning for date range queries
2. **Maintenance**: Drop old partitions instead of DELETE
3. **Parallel Queries**: Partitions can be scanned in parallel
4. **Index Efficiency**: Smaller indexes per partition

### Adding New Partitions

```sql
-- Manual (for future dates)
CREATE TABLE devto_analytics.daily_analytics_2027_01
PARTITION OF devto_analytics.daily_analytics
FOR VALUES FROM ('2027-01-01') TO ('2027-02-01');

-- Or re-run init_database.py to create next 12 months
```

### Monitoring

```sql
-- View all partitions
SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'devto_analytics' 
  AND tablename LIKE 'daily_analytics_%'
ORDER BY tablename;

-- View partition sizes
SELECT 
    schemaname || '.' || tablename as partition,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'devto_analytics'
  AND tablename LIKE 'daily_analytics_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Querying

No changes needed! Queries work transparently:

```python
# Query automatically uses partition pruning
stmt = select(daily_analytics).where(
    daily_analytics.c.date >= '2026-01-01'
)
```

PostgreSQL automatically scans only relevant partitions.

---

**Implementation**: `app/db/connection.py:init_schema()`  
**Management**: `app/init_database.py:create_monthly_partitions()`
