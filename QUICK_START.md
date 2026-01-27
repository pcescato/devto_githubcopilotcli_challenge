# DEV.to Analytics Platform - Quick Start

## 🚀 Start Everything

```bash
# Start entire stack
docker-compose up -d

# Check status
docker-compose ps
```

Expected output:
```
devto_fastapi    Up (healthy)   0.0.0.0:8000->8000/tcp
devto_postgres   Up (healthy)   0.0.0.0:5432->5432/tcp
devto_valkey     Up (healthy)   0.0.0.0:6379->6379/tcp
devto_superset   Up (healthy)   0.0.0.0:8088->8088/tcp
devto_dbgate     Up             0.0.0.0:3000->3000/tcp
```

## 📍 Access Points

| Service | URL | Credentials |
|---------|-----|-------------|
| **FastAPI API** | http://localhost:8000/docs | API Key: `devto-challenge-2026` |
| **Health Check** | http://localhost:8000/api/health | None |
| **Apache Superset** | http://localhost:8088 | admin / admin |
| **DbGate** | http://localhost:3000 | Auto-connected |
| **PostgreSQL** | localhost:5432 | devto / devto_secure_password |

## 🔑 API Examples

### Health Check (Public)
```bash
curl http://localhost:8000/api/health
```

### Quality Scores (Protected)
```bash
curl -H "X-API-Key: devto-challenge-2026" \
     http://localhost:8000/api/analytics/quality?limit=5
```

### Author DNA Report (Protected)
```bash
curl -H "X-API-Key: devto-challenge-2026" \
     http://localhost:8000/api/dna
```

### Sync Data from DEV.to (Protected)
```bash
curl -X POST \
     -H "X-API-Key: devto-challenge-2026" \
     -H "Content-Type: application/json" \
     -d '{"mode":"snapshot"}' \
     http://localhost:8000/api/sync
```

## 🛠️ Common Tasks

### View Logs
```bash
# FastAPI logs
docker logs -f devto_fastapi

# PostgreSQL logs
docker logs -f devto_postgres

# All services
docker-compose logs -f
```

### Restart Service
```bash
# Restart FastAPI only
docker-compose restart fastapi

# Restart all
docker-compose restart
```

### Rebuild After Code Changes
```bash
# Rebuild FastAPI image
docker-compose build fastapi

# Start with new image
docker-compose up -d fastapi
```

### Stop Everything
```bash
# Stop all services (keeps data)
docker-compose down

# Stop and remove volumes (deletes data!)
docker-compose down -v
```

## 🗄️ Database Access

### Using DbGate (Web UI)
1. Visit http://localhost:3000
2. Connection auto-configured to PostgreSQL
3. Browse tables in `devto_analytics` schema

### Using psql (Command Line)
```bash
docker exec -it devto_postgres psql -U devto -d devto_analytics
```

### SQL Queries
```sql
-- Count articles
SELECT COUNT(*) FROM devto_analytics.article_metrics;

-- Recent analytics
SELECT * FROM devto_analytics.daily_analytics 
ORDER BY analytics_date DESC LIMIT 10;

-- Article themes
SELECT theme_name, COUNT(*) 
FROM devto_analytics.author_themes t
JOIN devto_analytics.article_theme_mapping m ON t.id = m.theme_id
GROUP BY theme_name;
```

## 📊 Analytics Tools

### CLI Sismograph
```bash
# View article evolution
python3 sismograph.py --evolution 3180743

# Show velocity stats
python3 sismograph.py --velocity 3180743
```

### Theme Classification
```bash
# Classify all articles
python3 -m app.services.theme_service --classify-all

# Generate DNA report
python3 -m app.services.theme_service --report
```

### Data Sync
```bash
# Snapshot sync (quick, recent data)
python3 -m app.services.devto_service --snapshot

# Full sync (complete historical data)
python3 -m app.services.devto_service --full
```

## 🔧 Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs devto_fastapi

# Check environment
docker exec devto_fastapi env

# Verify database connection
docker exec devto_fastapi python -c "
from app.db.connection import get_engine
print(get_engine())
"
```

### Port Already in Use
```bash
# Find what's using port 8000
lsof -i :8000

# Stop the process (use actual PID from lsof output)
# kill -9 <PID>
```

### Reset Everything
```bash
# Nuclear option: Remove all containers and volumes
docker-compose down -v
docker-compose up -d

# Wait for health checks
watch docker-compose ps
```

## 📚 Documentation

- **Full Docs**: See README.md
- **API Reference**: API_DOCUMENTATION.md
- **Docker Setup**: FASTAPI_DOCKER.md
- **Superset**: SUPERSET_SETUP.md
- **Technical**: TECHNICAL_DOCUMENTATION.md

## 🎯 Next Steps

1. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your DEV.to API key
   ```

2. **Sync Your Data**
   ```bash
   # Set DEVTO_API_KEY in .env first!
   python3 -m app.services.devto_service --snapshot
   ```

3. **Explore API**
   - Visit http://localhost:8000/docs
   - Try endpoints with the "Authorize" button
   - Use API key: `devto-challenge-2026`

4. **Build Dashboards**
   - Login to Superset: http://localhost:8088
   - Add database connection
   - Create datasets from tables
   - Build visualizations

## 💡 Pro Tips

- Use `docker-compose logs -f SERVICE` to watch specific service logs
- Set `DEVTO_API_KEY` in `.env` before syncing data
- Change default passwords in `.env` for production
- Use `docker stats` to monitor resource usage
- Enable Caddy reverse proxy for production URLs

## 🆘 Need Help?

1. Check logs: `docker-compose logs`
2. Verify health: `curl http://localhost:8000/api/health`
3. Test database: `docker exec devto_postgres pg_isready`
4. Review docs in repository
5. Check GitHub issues

---

**Generated with GitHub Copilot CLI** 🚀
