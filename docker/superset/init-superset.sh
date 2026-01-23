#!/bin/bash
set -e

echo "🚀 Initializing Apache Superset..."

# Wait for database to be ready
echo "⏳ Waiting for PostgreSQL..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "✅ PostgreSQL is ready"

# Wait for Valkey to be ready
echo "⏳ Waiting for Valkey..."
while ! nc -z valkey 6379; do
  sleep 1
done
echo "✅ Valkey is ready"

# Initialize Superset database
echo "📊 Initializing Superset database..."
if [ ! -f /app/superset_home/.superset_initialized ]; then
  superset db upgrade
  
  # Create admin user
  echo "👤 Creating admin user..."
  superset fab create-admin \
    --username "${SUPERSET_ADMIN_USERNAME:-admin}" \
    --firstname "${SUPERSET_ADMIN_FIRSTNAME:-Admin}" \
    --lastname "${SUPERSET_ADMIN_LASTNAME:-User}" \
    --email "${SUPERSET_ADMIN_EMAIL:-admin@devto-analytics.local}" \
    --password "${SUPERSET_ADMIN_PASSWORD:-admin}" || true
  
  # Initialize Superset
  echo "🔧 Initializing Superset..."
  superset init
  
  # Import roles and permissions
  echo "🔐 Setting up roles and permissions..."
  superset import-directory /app/docker/import/ || true
  
  # Create DEV.to Analytics database connection
  echo "🔌 Creating database connection..."
  cat <<EOF | superset fab create-db
{
  "database_name": "DEV.to Analytics",
  "sqlalchemy_uri": "postgresql+psycopg2://${POSTGRES_USER:-devto}:${POSTGRES_PASSWORD:-devto_secure_password}@postgres:5432/${POSTGRES_DB:-devto_analytics}",
  "expose_in_sqllab": true,
  "allow_ctas": true,
  "allow_cvas": true,
  "allow_dml": true,
  "allow_multi_schema_metadata_fetch": true,
  "cache_timeout": 300,
  "extra": "{\"metadata_params\":{},\"engine_params\":{\"connect_args\":{\"options\":\"-c search_path=devto_analytics,public\"}}}",
  "impersonate_user": false,
  "server_cert": null
}
EOF
  
  # Mark as initialized
  touch /app/superset_home/.superset_initialized
  
  echo "✅ Superset initialization complete!"
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🎉 Superset is ready!"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📍 URL: http://localhost:8088"
  echo "👤 Username: ${SUPERSET_ADMIN_USERNAME:-admin}"
  echo "🔑 Password: ${SUPERSET_ADMIN_PASSWORD:-admin}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
else
  echo "✅ Superset already initialized"
fi

# Start Superset
echo "🚀 Starting Superset web server..."
