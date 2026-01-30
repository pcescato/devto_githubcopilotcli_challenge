# Docker Services - Quick Access Guide

## 🚀 All Services Running

Successfully deployed **6 Docker containers** with Caddy reverse proxy for friendly domain access.

## 📊 Access Points

### Via Caddy (Friendly Domains)

| Service | Domain | Description | Port |
|---------|--------|-------------|------|
| **Streamlit** | http://streamlit.local | Interactive analytics dashboard | 8501 |
| **FastAPI** | http://analytics.local | REST API with authentication | 8000 |
| **Superset** | http://dashboard.local | Business intelligence platform | 8088 |
| **DbGate** | http://db.local | Database management GUI | 3000 |

### Direct Access (localhost)

| Service | URL | Description |
|---------|-----|-------------|
| **Streamlit** | http://localhost:8501 | Streamlit dashboard |
| **FastAPI** | http://localhost:8000/docs | OpenAPI/Swagger documentation |
| **Superset** | http://localhost:8088 | Superset login (admin/admin) |
| **DbGate** | http://localhost:3000 | Database client |
| **PostgreSQL** | localhost:5432 | Direct database connection |
| **Valkey** | localhost:6379 | Redis-compatible cache |

## 🐳 Container Status

```bash
# Check all services
docker-compose ps

# Current status (all healthy):
✅ devto_postgres    - Up (healthy)
✅ devto_valkey      - Up (healthy)
✅ devto_fastapi     - Up (healthy)
✅ devto_superset    - Up (healthy)
✅ devto_dbgate      - Up
✅ devto_streamlit   - Up (healthy)
```

## 🔧 Common Commands

### Start/Stop Services

```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d streamlit

# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes data!)
docker-compose down -v

# Restart specific service
docker-compose restart streamlit
```

### View Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f streamlit
docker-compose logs -f fastapi

# Last 100 lines
docker-compose logs --tail=100 streamlit
```

### Rebuild Containers

```bash
# Rebuild all images
docker-compose build

# Rebuild specific service
docker-compose build streamlit

# Rebuild and restart
docker-compose up -d --build streamlit
```

### Health Checks

```bash
# Check Streamlit health
curl http://streamlit.local
curl http://localhost:8501/_stcore/health

# Check FastAPI health
curl http://analytics.local/api/health
curl http://localhost:8000/api/health

# Check Superset health
curl http://dashboard.local/health
curl http://localhost:8088/health
```

## 🎨 Streamlit Dashboard Pages

Access via http://streamlit.local or http://localhost:8501

1. **Welcome** (Main page)
   - Quick statistics overview
   - Database connection status
   - Navigation to specialized pages

2. **📊 Analytics**
   - Quality score rankings
   - Read time analysis
   - Engagement metrics
   - Reaction breakdown

3. **🧬 Author DNA**
   - Theme distribution
   - Performance by theme
   - Article classifications
   - Strategic insights

4. **📈 Evolution**
   - Global trends (7-365 days)
   - Individual article tracking
   - Engagement rate charts
   - Growth velocity analysis

5. **💬 Sentiment**
   - Comment sentiment analysis
   - Spam detection
   - Recent comments feed
   - Sentiment distribution

## 🔐 Authentication

### FastAPI API Key

Required for protected endpoints:

```bash
# Set header
X-API-Key: devto-challenge-2026

# Example with curl
curl -H "X-API-Key: devto-challenge-2026" \
     http://analytics.local/api/analytics/quality?limit=5
```

### Superset Login

- Username: `admin`
- Password: `admin`
- URL: http://dashboard.local

### Database Credentials

```env
POSTGRES_USER=devto
POSTGRES_PASSWORD=devto_secure_password
POSTGRES_DB=devto_analytics
POSTGRES_HOST=postgres (in Docker network)
POSTGRES_HOST=localhost (from host machine)
```

## 🔄 Data Sync

### Manual Sync

```bash
# Sync all data (articles, followers, comments)
docker-compose exec fastapi python -m app.services.devto_service --all

# Sync only articles
docker-compose exec fastapi python -m app.services.devto_service --snapshot

# Run NLP analysis
docker-compose exec fastapi python -m app.services.nlp_service

# Generate DNA report
docker-compose exec fastapi python -m app.services.theme_service --full
```

### Automated Sync (cron)

Already configured in crontab:
```bash
*/30 * * * * cd /root/projects/devto_githubcopilotcli_challenge && /root/projects/devto_githubcopilotcli_challenge/venv/bin/python -m app.services.devto_service --all
```

## 🌐 Caddy Configuration

### Reload Caddy

After updating Caddyfile:
```bash
sudo systemctl reload caddy
sudo systemctl status caddy
```

### Caddy Logs

```bash
# Access logs
sudo journalctl -u caddy -f

# Service-specific logs
sudo tail -f /var/log/caddy/streamlit.log
sudo tail -f /var/log/caddy/analytics.log
sudo tail -f /var/log/caddy/superset.log
```

### DNS (/etc/hosts)

Ensure these entries exist in `/etc/hosts`:
```
127.0.0.1 streamlit.local
127.0.0.1 analytics.local
127.0.0.1 db.local
127.0.0.1 dashboard.local
127.0.0.1 devto-analytics.local
```

## 🛠️ Troubleshooting

### Streamlit Not Loading

1. Check container status:
   ```bash
   docker-compose ps streamlit
   docker-compose logs streamlit
   ```

2. Check health endpoint:
   ```bash
   curl http://localhost:8501/_stcore/health
   ```

3. Restart container:
   ```bash
   docker-compose restart streamlit
   ```

### Database Connection Issues

1. Check PostgreSQL is healthy:
   ```bash
   docker-compose ps postgres
   ```

2. Test connection:
   ```bash
   docker-compose exec postgres psql -U devto -d devto_analytics -c "SELECT 1;"
   ```

3. Check environment variables:
   ```bash
   docker-compose exec streamlit env | grep POSTGRES
   ```

### Caddy Not Routing

1. Check Caddy is running:
   ```bash
   sudo systemctl status caddy
   ```

2. Test direct access first:
   ```bash
   curl http://localhost:8501
   ```

3. Reload Caddy configuration:
   ```bash
   sudo systemctl reload caddy
   ```

4. Check DNS resolution:
   ```bash
   ping streamlit.local
   ```

## 📚 Documentation

- **STREAMLIT_GUIDE.md** - Comprehensive Streamlit usage guide
- **API_DOCUMENTATION.md** - Complete REST API reference
- **SUPERSET_DASHBOARD_GUIDE.md** - Superset dashboard creation
- **FASTAPI_DOCKER.md** - Production Docker deployment
- **QUICK_START.md** - One-page quick reference

## 🎯 Quick Start

```bash
# 1. Start all services
docker-compose up -d

# 2. Wait for health checks (30-60 seconds)
docker-compose ps

# 3. Access dashboards
# - Streamlit: http://streamlit.local
# - Superset: http://dashboard.local (admin/admin)
# - API Docs: http://analytics.local/docs
# - Database: http://db.local

# 4. Sync data (first time)
docker-compose exec fastapi python -m app.services.devto_service --all
docker-compose exec fastapi python -m app.services.nlp_service
docker-compose exec fastapi python -m app.services.theme_service --full

# 5. Refresh Streamlit dashboard
# Click "🔄 Refresh Data" in sidebar or F5
```

## ✨ What's New

**Latest Addition: Streamlit in Docker (2026-01-30)**

- ✅ Streamlit service added to docker-compose.yml
- ✅ Accessible via http://streamlit.local (Caddy proxy)
- ✅ WebSocket support for real-time updates
- ✅ Health checks on /_stcore/health endpoint
- ✅ All Streamlit dependencies included in Dockerfile
- ✅ Auto-restart on failure
- ✅ Production-ready configuration

**Status:** All 6 containers running with 5/6 healthy
