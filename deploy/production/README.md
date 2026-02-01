# Production Blueprint Export

This directory contains **anonymized architectural snapshots** of the production deployment configuration for the Dev.to Analytics platform.

---

## ⚠️ CRITICAL: What This Directory is NOT

### ❌ **NOT a Backup**
These files are architectural snapshots for reference and reproduction purposes. They are **NOT** intended as a disaster recovery source. For backups:
- Use proper database backup tools (`pg_dump`, automated snapshots)
- Store backups in a separate, secure location
- Test your backup restoration procedure regularly

### ❌ **NOT Production-Ready As-Is**
These configurations **CANNOT** be deployed directly to a new environment without significant modifications:
- **Domains**: All references to `{{YOUR_DOMAIN}}` must be replaced with your actual domain
- **Networking**: Docker networks, port bindings, and internal routing must be reviewed
- **Volumes**: Data persistence paths need adjustment for your infrastructure
- **TLS Certificates**: Certificate paths (`{{PATH_TO_TLS_CERT}}`) must point to your actual certificates
- **Resource Limits**: Memory and CPU limits should be tuned for your specific hardware

### ❌ **NOT Containing Real Secrets**
Every token, password, API key, and secret has been **scrubbed and replaced** with placeholders:
- `{{CHANGE_ME_*}}` - Must be replaced with actual secure values
- **Never** commit real secrets to version control
- Use environment variables or secret management tools (Vault, AWS Secrets Manager, etc.)

---

## 📋 Files Included

### `docker-compose.yml`
Orchestration configuration for all services:
- **PostgreSQL**: Database with Alloy DB
- **Valkey (Redis)**: Cache and queue backend
- **FastAPI**: REST API backend
- **Streamlit**: Analytics dashboard UI
- **Authentik**: Identity and Access Management (IAM)
- **Wallabag**: Read-it-later service
- **DbGate**: Database management UI

### `Caddyfile`
Reverse proxy configuration with:
- TLS termination (Cloudflare Origin Certificates)
- Forward authentication via Authentik
- Route definitions for all subdomains
- Security headers and CORS policies

### `deploy_analytics.sh`
Production deployment script with:
- Pre-deployment validation
- Backup creation
- Service orchestration
- Database initialization
- Health checks

---

## 🔐 Required Environment Variables

The following environment variables **must** be configured before deployment:

### Database (PostgreSQL)
```bash
POSTGRES_HOST=localhost          # Database host
POSTGRES_PORT=5432               # Database port
POSTGRES_USER={{CHANGE_ME}}      # Database username
POSTGRES_PASSWORD={{CHANGE_ME}}  # Database password (STRONG)
DEVTO_DB_NAME=devto_analytics    # Database name for analytics
```

### Dev.to API
```bash
DEVTO_API_KEY={{CHANGE_ME}}      # Your Dev.to API key
                                 # Get from: https://dev.to/settings/extensions
```

### API Authentication
```bash
API_KEY={{CHANGE_ME}}            # API authentication key (min 32 chars)
DEVTO_APP_API_KEY={{CHANGE_ME}}  # Alternative API key if needed
```

### Authentik IAM
```bash
AUTHENTIK_SECRET_KEY={{CHANGE_ME}}           # Secret key (min 50 chars)
AUTHENTIK_BOOTSTRAP_PASSWORD={{CHANGE_ME}}   # Initial admin password
AUTHENTIK_BOOTSTRAP_TOKEN={{CHANGE_ME}}      # Bootstrap token (hex 64 chars)
AUTHENTIK_DB_NAME=authentik                  # Authentik database name
AUTHENTIK_DB_USER={{CHANGE_ME}}              # Authentik DB user
AUTHENTIK_DB_PASSWORD={{CHANGE_ME}}          # Authentik DB password
```

### Cache (Valkey/Redis)
```bash
DEVTO_VALKEY_PASSWORD={{CHANGE_ME}}  # Redis password (STRONG)
```

### Domain Configuration
```bash
DOMAIN={{YOUR_DOMAIN}}               # Base domain (e.g., example.com)
```

### Optional: Database Management
```bash
DBGATE_USER={{CHANGE_ME}}            # DbGate username
DBGATE_PASSWORD={{CHANGE_ME}}        # DbGate password
```

---

## 🏗️ Architecture: Request Flow

### Public Routes (No Authentication)
```
Internet → Cloudflare CDN → Caddy → Service
                              ↓
                    ┌─────────┴──────────┐
                    │                    │
              analytics.{{DOMAIN}}   wallabag.{{DOMAIN}}
                    │                    │
                FastAPI              Wallabag
```

### Protected Routes (Authentik Forward Auth)
```
Internet → Cloudflare CDN → Caddy → Authentik Forward Auth
                              ↓              ↓
                         (checks auth)  (redirects if not logged in)
                              ↓
                    ┌─────────┴──────────┐
                    │                    │
           streamlit.{{DOMAIN}}    dbgate.{{DOMAIN}}
                    │                    │
                Streamlit             DbGate
```

### Authentication Flow (Authentik)
```
1. User visits protected route (e.g., streamlit.{{DOMAIN}})
   ↓
2. Caddy sends forward_auth request to Authentik
   ↓
3. Authentik checks for valid session cookie
   ↓
4a. ✅ Valid → Authentik responds with 200 + user headers
    ↓
    Caddy proxies request to backend with auth headers
    
4b. ❌ Invalid → Authentik responds with 302 redirect
    ↓
    User redirected to auth.{{DOMAIN}}/login
    ↓
    After login, redirected back to original URL
```

### Key Components

#### Caddy (Reverse Proxy)
- **Port**: 443 (HTTPS)
- **Role**: 
  - TLS termination
  - Reverse proxy routing
  - Forward auth integration
  - Security headers injection

#### Authentik (IAM)
- **Ports**: 
  - 9000 (HTTP - internal)
  - 9443 (HTTPS - internal)
- **Role**:
  - User authentication
  - OAuth2/OIDC provider
  - Forward auth validation
  - SSO cookie management (`.{{DOMAIN}}`)

#### FastAPI Backend
- **Port**: 8000 (internal)
- **Role**:
  - REST API endpoints
  - Data aggregation
  - Business logic

#### Streamlit Dashboard
- **Port**: 8501 (internal)
- **Role**:
  - Interactive analytics UI
  - Data visualization
  - Report generation

#### PostgreSQL Database
- **Port**: 5432 (internal)
- **Role**:
  - Primary data store
  - Partitioned tables (daily_analytics)
  - Vector search (pgvector)

#### Valkey (Redis)
- **Port**: 6379 (internal)
- **Role**:
  - Session cache
  - Celery queue
  - Rate limiting

---

## 🚀 Deployment Checklist

Before deploying to a new environment:

### 1. Prerequisites
- [ ] Docker Engine 20.10+ installed
- [ ] Docker Compose V2 installed
- [ ] Caddy 2.7+ installed (or use Docker)
- [ ] Valid TLS certificates (Cloudflare Origin or Let's Encrypt)
- [ ] Domain DNS configured (A/AAAA records)

### 2. Configuration
- [ ] Copy `.env.example` to `.env`
- [ ] Replace ALL `{{CHANGE_ME_*}}` placeholders with secure values
- [ ] Update `{{YOUR_DOMAIN}}` with your actual domain
- [ ] Update `{{PATH_TO_TLS_CERT}}` with certificate paths
- [ ] Review and adjust resource limits (CPU, memory)
- [ ] Configure volume mount paths

### 3. Secrets Management
- [ ] Generate strong passwords (min 32 characters, mixed case + symbols)
- [ ] Generate Authentik secret key: `openssl rand -hex 50`
- [ ] Generate Authentik bootstrap token: `openssl rand -hex 32`
- [ ] Store secrets in a secure vault (not in Git)

### 4. Network Configuration
- [ ] Verify Docker network: `backend` exists or create it
- [ ] Check port conflicts on host
- [ ] Configure firewall rules (allow 443, block 5432/6379/etc)
- [ ] Set up Cloudflare Tunnel or direct DNS (if not using CDN)

### 5. Initial Deployment
- [ ] Run `docker-compose up -d postgres valkey` first
- [ ] Wait for databases to be healthy
- [ ] Run database migrations/initialization
- [ ] Start remaining services: `docker-compose up -d`
- [ ] Verify all containers are healthy: `docker ps`

### 6. Authentik Setup
- [ ] Access `auth.{{DOMAIN}}`
- [ ] Complete initial setup wizard
- [ ] Create user groups (Admins, Judges)
- [ ] Configure proxy providers for Streamlit and DbGate
- [ ] Create applications and bind to embedded outpost
- [ ] Test forward authentication

### 7. Validation
- [ ] Test public routes (analytics API, wallabag)
- [ ] Test protected routes (streamlit, dbgate) - should redirect to auth
- [ ] Test login flow and SSO across subdomains
- [ ] Verify TLS certificates are valid
- [ ] Check application logs for errors
- [ ] Run API health checks

---

## 🔧 Customization Guide

### Adjusting Memory Limits
Edit `docker-compose.yml` under each service's `deploy.resources.limits`:

```yaml
deploy:
  resources:
    limits:
      memory: 768M  # Adjust based on available RAM
```

**Recommended minimums**:
- PostgreSQL: 512M (1GB for production)
- Authentik Server: 768M
- Authentik Worker: 512M
- FastAPI: 384M
- Streamlit: 512M
- Valkey: 128M

### Adding New Subdomains
1. Add DNS record: `newapp.{{DOMAIN}} → server_ip`
2. Add Caddy block in `Caddyfile`:
```caddyfile
newapp.{{YOUR_DOMAIN}} {
    tls {{PATH_TO_TLS_CERT}}/cert.pem {{PATH_TO_TLS_CERT}}/key.pem
    
    # Optional: protect with Authentik
    forward_auth localhost:9000 {
        uri /outpost.goauthentik.io/auth/caddy
        copy_headers X-authentik-username X-authentik-groups
    }
    
    reverse_proxy localhost:PORT
}
```
3. Reload Caddy: `systemctl reload caddy`

### Changing Database Host
If using external PostgreSQL (AWS RDS, GCP Cloud SQL):

1. Update `.env`:
```bash
POSTGRES_HOST=your-db-instance.region.rds.amazonaws.com
POSTGRES_PORT=5432
```

2. Remove `postgres` service from `docker-compose.yml`

3. Ensure network connectivity (VPC, security groups)

---

## 📊 Monitoring & Maintenance

### Health Checks
All services have built-in health checks:
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Logs
View service logs:
```bash
docker logs -f SERVICE_NAME
docker logs -f --tail 100 authentik_server
```

### Database Backups
Automated backup script (recommended):
```bash
#!/bin/bash
pg_dump -h localhost -U $POSTGRES_USER $DEVTO_DB_NAME | \
  gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

### Updates
Check for updates:
```bash
docker-compose pull
docker-compose up -d  # Recreates containers with new images
```

---

## 🆘 Troubleshooting

### Service Won't Start
1. Check logs: `docker logs SERVICE_NAME`
2. Verify dependencies are healthy
3. Check resource availability: `docker stats`
4. Validate configuration: `docker-compose config`

### Authentication Issues
1. Verify Authentik is running: `docker ps | grep authentik`
2. Check embedded outpost logs
3. Verify provider configuration in Authentik UI
4. Test forward auth endpoint: `curl -I http://localhost:9000/outpost.goauthentik.io/auth/caddy`

### Database Connection Errors
1. Check PostgreSQL is healthy
2. Verify credentials in `.env`
3. Test connection: `psql -h localhost -U $POSTGRES_USER $DEVTO_DB_NAME`
4. Check network connectivity between containers

### TLS Certificate Errors
1. Verify certificate files exist at specified paths
2. Check certificate validity: `openssl x509 -in cert.pem -text -noout`
3. Ensure Caddy has read permissions
4. Validate Caddyfile syntax: `caddy validate --config /etc/caddy/Caddyfile`

---

## 📚 Additional Resources

- **Authentik Documentation**: https://goauthentik.io/docs/
- **Caddy Documentation**: https://caddyserver.com/docs/
- **Docker Compose Reference**: https://docs.docker.com/compose/
- **PostgreSQL Documentation**: https://www.postgresql.org/docs/

---

## 🔒 Security Best Practices

1. **Never commit secrets**: Use `.env` files and add them to `.gitignore`
2. **Rotate credentials regularly**: Change passwords every 90 days minimum
3. **Use strong passwords**: Min 32 characters, mixed case, symbols, numbers
4. **Enable 2FA**: For all admin accounts (Authentik, DbGate, etc.)
5. **Restrict network access**: Firewall rules, VPC security groups
6. **Keep software updated**: Regularly update Docker images
7. **Monitor logs**: Set up log aggregation and alerting
8. **Backup encryption**: Encrypt backups at rest and in transit
9. **Principle of least privilege**: Grant minimum necessary permissions
10. **Audit access**: Review Authentik logs for suspicious activity

---

## 📄 License

This configuration blueprint is provided as-is for reference purposes. Adapt it to your specific requirements and infrastructure.

---

**Last Updated**: 2026-02-01  
**Version**: 1.0.0  
**Status**: Production Blueprint
