# Apache Superset Setup - PostgreSQL Integration

## ✅ Status: WORKING

Superset is now successfully integrated with PostgreSQL 18 and fully operational.

## Configuration Summary

### Docker Compose Changes

1. **Image Tag**: Changed from `apache/superset:latest` to `apache/superset:${SUPERSET_TAG:-latest-dev}`
   - The `-dev` suffix includes `psycopg2-binary` required for PostgreSQL connections
   - Default: `latest-dev`
   - Can be overridden: `export SUPERSET_TAG=5.0.0-dev`

2. **Init Script**: Fixed `/app/docker/init-superset.sh`
   - Replaced `nc` (netcat) checks with Python socket connections (nc not available in image)
   - Proper database initialization with `superset db upgrade`
   - Admin user creation via `superset fab create-admin`
   - Initialization with `superset init`
   - Gunicorn server start with proper configuration

3. **Environment Variables** (added to `.env.example`):
   ```bash
   SUPERSET_TAG=latest-dev
   SUPERSET_PORT=8088
   SUPERSET_ADMIN_USERNAME=admin
   SUPERSET_ADMIN_PASSWORD=admin
   SUPERSET_ADMIN_EMAIL=admin@devto-analytics.local
   SUPERSET_SECRET_KEY=CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY
   ```

## Access Information

- **URL**: http://localhost:8088
- **Username**: `admin` (default, configurable via environment)
- **Password**: `admin` (default, configurable via environment)
- **Health Endpoint**: http://localhost:8088/health

## Database Connection

Superset uses PostgreSQL for its metadata:
- **Connection String**: `postgresql+psycopg2://devto:password@postgres:5432/devto_analytics`
- **Driver**: `psycopg2-binary` (included in `-dev` images)
- **Schema**: Superset creates its own tables in the database

To connect to your DEV.to Analytics data:
1. Login to Superset
2. Go to Settings → Database Connections
3. Add database with same connection string
4. Test connection
5. Start creating dashboards!

## Troubleshooting

### Issue: Container unhealthy

**Symptoms**:
- Container shows `(unhealthy)` status
- Logs show `nc: command not found`
- Logs show `ModuleNotFoundError: No module named 'psycopg2'`

**Solution**:
1. Use `-dev` image tag (includes psycopg2-binary)
2. Use Python socket checks instead of nc in init script

### Issue: Init script fails

**Solution**:
- Check PostgreSQL is healthy first: `docker-compose ps postgres`
- Check Valkey is healthy: `docker-compose ps valkey`
- Review logs: `docker logs devto_superset`

## Verification Commands

```bash
# Check container status
docker-compose ps superset

# Check health
curl http://localhost:8088/health

# View logs
docker logs devto_superset --tail 50

# Restart if needed
docker-compose restart superset

# Clean restart
docker-compose down
docker-compose up -d
```

## Next Steps

1. **Login**: Visit http://localhost:8088 with admin credentials
2. **Add Database Connection**: Settings → Database Connections → + Database
3. **Create Datasets**: From tables (daily_analytics, article_metrics, etc.)
4. **Build Charts**: Create visualizations from datasets
5. **Create Dashboard**: Combine charts into analytics dashboard

## Production Notes

- Change default admin password via environment variables
- Set strong `SUPERSET_SECRET_KEY`
- Use Valkey for rate limiting (already configured)
- Enable HTTPS with reverse proxy (Caddy configured in docker-compose)
- Configure Content Security Policy (CSP) for production

## References

- [Superset Documentation](https://superset.apache.org/docs/intro)
- [PostgreSQL Driver](https://superset.apache.org/docs/databases/postgres)
- [Docker Image Tags](https://hub.docker.com/r/apache/superset/tags)
