#!/bin/bash
set -e

echo "🚀 Initializing Apache Superset..."

# Wait for database to be ready (using Python instead of nc)
echo "⏳ Waiting for PostgreSQL..."
python3 <<EOF
import socket
import time
import sys

def wait_for_service(host, port, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect((host, port))
            sock.close()
            return True
        except (socket.error, socket.timeout):
            time.sleep(1)
    return False

if not wait_for_service('postgres', 5432):
    print("❌ PostgreSQL not ready after 60s")
    sys.exit(1)
EOF
echo "✅ PostgreSQL is ready"

# Wait for Valkey to be ready
echo "⏳ Waiting for Valkey..."
python3 <<EOF
import socket
import time
import sys

def wait_for_service(host, port, timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            sock.connect((host, port))
            sock.close()
            return True
        except (socket.error, socket.timeout):
            time.sleep(1)
    return False

if not wait_for_service('valkey', 6379):
    print("❌ Valkey not ready after 60s")
    sys.exit(1)
EOF
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

# Start Superset web server
echo "🚀 Starting Superset web server..."
exec gunicorn \
  --bind 0.0.0.0:8088 \
  --workers 4 \
  --timeout 300 \
  --limit-request-line 0 \
  --limit-request-field_size 0 \
  --access-logfile - \
  --error-logfile - \
  "superset.app:create_app()"
