# Docker Infrastructure for DEV.to Analytics

Production-ready Docker Compose stack with PostgreSQL 18, Valkey (Redis alternative), DbGate, and Apache Superset.

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Caddy (for reverse proxy, optional)

### Installation

1. **Configure environment variables:**

```bash
cp .env.example .env
# Edit .env with your credentials
```

2. **Start the stack:**

```bash
docker-compose up -d
```

3. **Initialize the database schema:**

```bash
# Wait for PostgreSQL to be ready
docker-compose logs -f postgres

# Run initialization script
cd app
pip install -r requirements.txt
python3 init_database.py
```

4. **Access the services:**

- **PostgreSQL**: `localhost:5432`
- **DbGate** (Database UI): http://localhost:3000
- **Superset** (Analytics): http://localhost:8088
- **FastAPI** (planned): http://localhost:8000

## 📦 Services

### PostgreSQL 18

**Image**: `postgres:18-alpine`  
**Port**: 5432  
**Volume**: `devto_postgres_data`

Features:
- Optimized configuration for analytics workload
- Performance tuning (shared_buffers, work_mem, etc.)
- pgvector extension support
- Automatic health checks
- Daily log rotation

Configuration:
- `docker/postgres/postgresql.conf` - Performance settings
- `docker/postgres/init.sql` - Database initialization

### Valkey 8.0

**Image**: `valkey/valkey:8.0-alpine`  
**Port**: 6379  
**Volume**: `devto_valkey_data`

100% open-source Redis alternative for:
- Superset caching
- Session storage
- Query result caching
- FastAPI caching (planned)

Configuration:
- `docker/valkey/valkey.conf` - Cache settings
- LRU eviction policy
- 512MB max memory
- RDB snapshots enabled

### DbGate

**Image**: `dbgate/dbgate:latest`  
**Port**: 3000  
**Volume**: `devto_dbgate_data`

Web-based database client features:
- SQL query editor
- Visual query builder
- Data export (CSV, JSON, Excel)
- Schema visualization
- Table data editor

Default connection to PostgreSQL is pre-configured.

### Apache Superset

**Image**: `apache/superset:latest`  
**Port**: 8088  
**Volume**: `devto_superset_data`

Business intelligence platform features:
- Interactive dashboards
- SQL Lab for ad-hoc queries
- Chart builder (50+ visualization types)
- Row-level security
- Scheduled reports

Default credentials:
- Username: `admin` (from .env)
- Password: `admin` (from .env)

Configuration:
- `docker/superset/superset_config.py` - Main config
- `docker/superset/init-superset.sh` - Initialization script

## 🌐 Reverse Proxy (Caddyfile)

The `Caddyfile` provides reverse proxy for all services with:
- Automatic HTTPS (disabled for local development)
- Custom domains via `/etc/hosts`
- Security headers
- Compression (gzip, zstd)
- Request logging

### Setup Local Domains

Add to `/etc/hosts`:

```bash
127.0.0.1 analytics.local
127.0.0.1 db.local
127.0.0.1 dashboard.local
127.0.0.1 devto-analytics.local
```

### Install Caddy (optional)

```bash
# Ubuntu/Debian
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy

# macOS
brew install caddy

# Run Caddy
caddy run --config Caddyfile
```

Access via domains:
- **FastAPI**: http://analytics.local
- **DbGate**: http://db.local
- **Superset**: http://dashboard.local

## 🔧 Management Commands

### Start/Stop Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d postgres

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ data loss)
docker-compose down -v
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f superset

# Last 100 lines
docker-compose logs --tail=100 postgres
```

### Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U devto -d devto_analytics

# Run SQL file
docker-compose exec -T postgres psql -U devto -d devto_analytics < schema.sql

# Create backup
docker-compose exec postgres pg_dump -U devto devto_analytics > backup.sql

# Restore backup
docker-compose exec -T postgres psql -U devto -d devto_analytics < backup.sql

# Check table sizes
docker-compose exec postgres psql -U devto -d devto_analytics -c "SELECT * FROM devto_analytics.get_table_sizes();"
```

### Valkey Operations

```bash
# Connect to Valkey CLI
docker-compose exec valkey valkey-cli -a valkey_secure_password

# Check memory usage
docker-compose exec valkey valkey-cli -a valkey_secure_password INFO memory

# Flush cache (⚠️ clears all data)
docker-compose exec valkey valkey-cli -a valkey_secure_password FLUSHALL
```

### Superset Operations

```bash
# Reinitialize Superset
docker-compose exec superset superset db upgrade
docker-compose exec superset superset init

# Create new admin user
docker-compose exec superset superset fab create-admin

# Import dashboards
docker-compose exec superset superset import-dashboards -p /app/dashboards/
```

## 🔍 Health Checks

All services include health checks:

```bash
# Check service health
docker-compose ps

# Detailed health status
docker inspect devto_postgres --format='{{.State.Health.Status}}'
docker inspect devto_valkey --format='{{.State.Health.Status}}'
```

## 📊 Performance Monitoring

### PostgreSQL

```bash
# Active queries
docker-compose exec postgres psql -U devto -d devto_analytics -c "
SELECT pid, usename, application_name, state, query 
FROM pg_stat_activity 
WHERE datname = 'devto_analytics';
"

# Slow queries (requires pg_stat_statements)
docker-compose exec postgres psql -U devto -d devto_analytics -c "
SELECT * FROM devto_analytics.query_performance LIMIT 10;
"

# Database size
docker-compose exec postgres psql -U devto -d devto_analytics -c "
SELECT * FROM devto_analytics.get_db_stats();
"
```

### Valkey

```bash
# Statistics
docker-compose exec valkey valkey-cli -a valkey_secure_password INFO stats

# Connected clients
docker-compose exec valkey valkey-cli -a valkey_secure_password CLIENT LIST

# Key count
docker-compose exec valkey valkey-cli -a valkey_secure_password DBSIZE
```

## 🔒 Security

### Production Checklist

- [ ] Change all default passwords in `.env`
- [ ] Generate strong `SUPERSET_SECRET_KEY` (32+ chars)
- [ ] Enable SSL for PostgreSQL
- [ ] Configure firewall rules
- [ ] Enable Caddy automatic HTTPS
- [ ] Add basic auth to DbGate
- [ ] Configure Superset authentication (OAuth, LDAP)
- [ ] Enable Docker secrets instead of .env
- [ ] Regular backup schedule
- [ ] Monitor logs for suspicious activity

### Generate Secure Keys

```bash
# PostgreSQL password
openssl rand -base64 32

# Valkey password
openssl rand -base64 32

# Superset secret key
openssl rand -base64 48
```

## 🐛 Troubleshooting

### PostgreSQL won't start

```bash
# Check logs
docker-compose logs postgres

# Common issues:
# - Port 5432 already in use
# - Invalid postgresql.conf syntax
# - Insufficient memory

# Reset database (⚠️ data loss)
docker-compose down -v
docker-compose up -d postgres
```

### Superset initialization fails

```bash
# Reinitialize manually
docker-compose exec superset /app/docker/init-superset.sh

# Clear initialization flag
docker-compose exec superset rm /app/superset_home/.superset_initialized

# Restart
docker-compose restart superset
```

### Valkey connection refused

```bash
# Check password
docker-compose logs valkey | grep requirepass

# Test connection
docker-compose exec valkey valkey-cli -a $VALKEY_PASSWORD PING
```

### DbGate can't connect

```bash
# Wait for PostgreSQL
docker-compose up -d postgres
docker-compose logs -f postgres | grep "ready to accept connections"

# Then start DbGate
docker-compose up -d dbgate
```

## 📈 Scaling

### Horizontal Scaling (planned)

```yaml
# Add to docker-compose.yml for FastAPI
fastapi:
  deploy:
    replicas: 3
    resources:
      limits:
        cpus: '1'
        memory: 512M
```

### Vertical Scaling

Adjust PostgreSQL settings in `.env`:

```bash
# For 8GB RAM server
POSTGRES_SHARED_BUFFERS=2GB
POSTGRES_EFFECTIVE_CACHE_SIZE=6GB
POSTGRES_MAINTENANCE_WORK_MEM=512MB
POSTGRES_WORK_MEM=32MB
```

## 📚 References

- [PostgreSQL 18 Documentation](https://www.postgresql.org/docs/18/)
- [Valkey Documentation](https://valkey.io/docs/)
- [Apache Superset Documentation](https://superset.apache.org/docs/)
- [DbGate Documentation](https://dbgate.org/docs/)
- [Caddy Documentation](https://caddyserver.com/docs/)

## 📄 Files

```
docker/
├── postgres/
│   ├── postgresql.conf      # Performance tuning
│   └── init.sql             # Database initialization
├── valkey/
│   └── valkey.conf          # Cache configuration
└── superset/
    ├── init-superset.sh     # Initialization script
    └── superset_config.py   # Superset settings

docker-compose.yml           # Service definitions
Caddyfile                    # Reverse proxy config
.env                         # Environment variables
.env.example                 # Template
```

---

**Status**: Production Ready ✅  
**Last Updated**: 2026-01-23
