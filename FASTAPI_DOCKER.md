# FastAPI Production Deployment with Docker

## ✅ Status: Production Ready

The FastAPI application is now running in a production-ready Docker container with Gunicorn and uvicorn workers.

## Configuration

### Docker Setup

**Image**: Python 3.11 slim
**Server**: Gunicorn with 4 uvicorn workers
**Port**: 8000 (exposed to host for Caddy reverse proxy)
**User**: Non-root appuser (UID 1000)

### Container Details

- **Name**: `devto_fastapi`
- **Health Check**: `/api/health` endpoint (30s interval)
- **Auto-restart**: `unless-stopped`
- **Dependencies**: PostgreSQL + Valkey (healthy)

### Environment Variables

All configuration via `.env`:
```bash
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=devto
POSTGRES_PASSWORD=devto_secure_password
POSTGRES_DB=devto_analytics

# Valkey (Redis)
VALKEY_HOST=valkey
VALKEY_PORT=6379
VALKEY_PASSWORD=valkey_secure_password

# DEV.to API
DEVTO_API_KEY=your_api_key

# API Authentication
API_KEY=devto-challenge-2026
```

## Usage

### Start Stack

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker logs devto_fastapi --follow
```

### Stop Stack

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: Deletes data!)
docker-compose down -v
```

### Rebuild After Changes

```bash
# Rebuild FastAPI image
docker-compose build fastapi

# Restart with new image
docker-compose up -d fastapi
```

## Verification

### Health Check

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "database": "connected",
  "timestamp": "2026-01-27T22:48:24.811145Z",
  "version": "1.0.0"
}
```

### API Info

```bash
curl http://localhost:8000/
```

### Test Authenticated Endpoint

```bash
curl -H "X-API-Key: devto-challenge-2026" \
     http://localhost:8000/api/analytics/quality?limit=3
```

### OpenAPI Documentation

Visit: http://localhost:8000/docs

## Caddy Integration

Caddy runs **on the host** (not in Docker) and reverse proxies to the FastAPI container:

**Caddyfile**:
```
analytics.local {
    reverse_proxy localhost:8000 {
        health_uri /health
        health_interval 10s
        health_timeout 5s
    }
}
```

**DNS Setup** (local development):
```bash
# /etc/hosts
127.0.0.1 analytics.local
```

**Access**:
- Direct: http://localhost:8000
- Via Caddy: http://analytics.local

## Architecture

```
┌─────────────────────────────────────────────────┐
│               HOST MACHINE                      │
│                                                 │
│  ┌─────────────┐                               │
│  │   Caddy     │ (Port 80/443)                 │
│  │   Proxy     │                               │
│  └──────┬──────┘                               │
│         │                                       │
│         │ Reverse Proxy                         │
│         ▼                                       │
│  ┌─────────────────────────────────────────┐  │
│  │         Docker Network                   │  │
│  │                                          │  │
│  │  ┌──────────────┐    ┌──────────────┐  │  │
│  │  │   FastAPI    │    │  PostgreSQL  │  │  │
│  │  │   Gunicorn   │◄───┤  + pgvector  │  │  │
│  │  │   :8000      │    │              │  │  │
│  │  └──────┬───────┘    └──────────────┘  │  │
│  │         │                                │  │
│  │         │            ┌──────────────┐  │  │
│  │         └────────────┤    Valkey    │  │  │
│  │                      │   (Redis)    │  │  │
│  │                      └──────────────┘  │  │
│  │                                         │  │
│  │  ┌──────────────┐    ┌──────────────┐  │  │
│  │  │   Superset   │    │   DbGate     │  │  │
│  │  │   :8088      │    │   :3000      │  │  │
│  │  └──────────────┘    └──────────────┘  │  │
│  └─────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

## Production Deployment

### Security Hardening

1. **Change default credentials**:
   ```bash
   # Generate strong passwords
   openssl rand -base64 32
   
   # Update .env
   POSTGRES_PASSWORD=<generated_password>
   VALKEY_PASSWORD=<generated_password>
   API_KEY=<generated_api_key>
   ```

2. **Enable HTTPS** (Caddy):
   ```
   # In Caddyfile, remove 'auto_https off'
   # Add email for Let's Encrypt
   {
       email admin@yourdomain.com
   }
   ```

3. **Use real domain**:
   ```
   api.yourdomain.com {
       reverse_proxy localhost:8000
   }
   ```

### Performance Tuning

**Gunicorn Workers**:
- Current: 4 workers
- Formula: `(2 * CPU_CORES) + 1`
- Adjust in `Dockerfile` CMD line

**Database Connection Pool**:
- Configured in `app/api/main.py`
- Current: `pool_size=20, max_overflow=10`

**Container Resources**:
```yaml
# docker-compose.yml
fastapi:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G
      reservations:
        cpus: '1.0'
        memory: 1G
```

## Monitoring

### Container Stats

```bash
docker stats devto_fastapi
```

### Logs

```bash
# Follow logs
docker logs -f devto_fastapi

# Last 100 lines
docker logs --tail 100 devto_fastapi

# Since timestamp
docker logs --since 30m devto_fastapi
```

### Health Checks

```bash
# Check health status
docker inspect devto_fastapi | jq '.[0].State.Health'

# All container health
docker-compose ps
```

## Troubleshooting

### Container won't start

```bash
# Check logs
docker logs devto_fastapi

# Check environment
docker exec devto_fastapi env

# Test database connection
docker exec devto_fastapi python -c "
from app.db.connection import get_engine
engine = get_engine()
print('Database connected!')
"
```

### Port already in use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Database connection errors

```bash
# Check PostgreSQL health
docker exec devto_postgres pg_isready -U devto

# Test connection from FastAPI container
docker exec devto_fastapi nc -zv postgres 5432
```

## Files

- `Dockerfile` - FastAPI production image
- `docker-compose.yml` - Full stack orchestration
- `app/api/main.py` - FastAPI application
- `Caddyfile` - Reverse proxy configuration
- `.env` - Environment variables (not in git)

## Migration from Dev Mode

**Old** (development):
```bash
uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
```

**New** (production):
```bash
docker-compose up -d
```

The API behavior is identical - Caddy continues to proxy to localhost:8000, but now it's served by a production-ready container instead of the dev server.

## References

- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Uvicorn Workers](https://www.uvicorn.org/#running-with-gunicorn)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/docker/)
- [Docker Compose](https://docs.docker.com/compose/)
