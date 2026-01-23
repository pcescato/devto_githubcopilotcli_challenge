-- PostgreSQL Initialization Script for DEV.to Analytics
-- This script runs automatically when the container is first created

\echo '🚀 Initializing DEV.to Analytics Database...'

-- Create extensions
\echo '📦 Installing extensions...'
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- Try to create pgvector extension (may fail if not installed)
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS "vector";
    RAISE NOTICE '✅ pgvector extension installed';
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING '⚠️  pgvector extension not available - install postgresql-18-pgvector package';
END
$$;

-- Create schema
\echo '🏗️  Creating schema...'
CREATE SCHEMA IF NOT EXISTS devto_analytics;

-- Set default schema
SET search_path TO devto_analytics, public;

-- Create a read-only role for analytics tools
\echo '👤 Creating roles...'
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_readonly') THEN
        CREATE ROLE analytics_readonly;
        RAISE NOTICE '✅ Created analytics_readonly role';
    END IF;
END
$$;

-- Grant permissions
GRANT USAGE ON SCHEMA devto_analytics TO analytics_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA devto_analytics TO analytics_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA devto_analytics GRANT SELECT ON TABLES TO analytics_readonly;

-- Create a read-write role for the application
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_app') THEN
        CREATE ROLE analytics_app;
        RAISE NOTICE '✅ Created analytics_app role';
    END IF;
END
$$;

GRANT USAGE, CREATE ON SCHEMA devto_analytics TO analytics_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA devto_analytics TO analytics_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA devto_analytics TO analytics_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA devto_analytics GRANT ALL ON TABLES TO analytics_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA devto_analytics GRANT ALL ON SEQUENCES TO analytics_app;

-- Create utility functions
\echo '⚙️  Creating utility functions...'

-- Function to calculate table sizes
CREATE OR REPLACE FUNCTION devto_analytics.get_table_sizes()
RETURNS TABLE (
    schema_name TEXT,
    table_name TEXT,
    total_size TEXT,
    table_size TEXT,
    indexes_size TEXT,
    row_count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        schemaname::TEXT,
        tablename::TEXT,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))::TEXT as total_size,
        pg_size_pretty(pg_relation_size(schemaname||'.'||tablename))::TEXT as table_size,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename))::TEXT as indexes_size,
        (SELECT n_live_tup FROM pg_stat_user_tables WHERE schemaname = t.schemaname AND tablename = t.tablename) as row_count
    FROM pg_tables t
    WHERE schemaname = 'devto_analytics'
    ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get database statistics
CREATE OR REPLACE FUNCTION devto_analytics.get_db_stats()
RETURNS TABLE (
    stat_name TEXT,
    stat_value TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 'Database Size'::TEXT, pg_size_pretty(pg_database_size(current_database()))::TEXT
    UNION ALL
    SELECT 'Total Tables'::TEXT, COUNT(*)::TEXT FROM pg_tables WHERE schemaname = 'devto_analytics'
    UNION ALL
    SELECT 'Total Indexes'::TEXT, COUNT(*)::TEXT FROM pg_indexes WHERE schemaname = 'devto_analytics'
    UNION ALL
    SELECT 'Active Connections'::TEXT, COUNT(*)::TEXT FROM pg_stat_activity WHERE datname = current_database()
    UNION ALL
    SELECT 'PostgreSQL Version'::TEXT, version()::TEXT;
END;
$$ LANGUAGE plpgsql;

-- Create performance monitoring view
CREATE OR REPLACE VIEW devto_analytics.query_performance AS
SELECT 
    queryid,
    LEFT(query, 100) as query_snippet,
    calls,
    ROUND(total_exec_time::numeric, 2) as total_time_ms,
    ROUND(mean_exec_time::numeric, 2) as mean_time_ms,
    ROUND(min_exec_time::numeric, 2) as min_time_ms,
    ROUND(max_exec_time::numeric, 2) as max_time_ms,
    ROUND(stddev_exec_time::numeric, 2) as stddev_time_ms,
    rows as total_rows
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY total_exec_time DESC
LIMIT 50;

\echo '✅ Database initialization complete!'
\echo ''
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '📊 DEV.to Analytics Database Ready'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo '📍 Database: devto_analytics'
\echo '📍 Schema: devto_analytics'
\echo '📍 Extensions: uuid-ossp, pg_trgm, btree_gin, btree_gist'
\echo '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━'
\echo ''
