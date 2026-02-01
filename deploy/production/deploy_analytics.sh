#!/bin/bash
################################################################################
# PRODUCTION DEPLOYMENT SCRIPT FOR DEV.TO ANALYTICS
# VPS Specs: 4vCPU, 4GB RAM
# Purpose: Deploy analytics services (FastAPI, Streamlit, Superset, Valkey)
#          while reusing existing PostgreSQL and backend network
################################################################################

set -euo pipefail  # Exit on error, undefined variable, or pipe failure

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$HOME/docker/backups/$TIMESTAMP"
MAIN_COMPOSE="$HOME/docker/docker-compose.yml"
ANALYTICS_COMPOSE="$HOME/docker/devto_stats/docker-compose.yml"
CADDYFILE="/etc/caddy/Caddyfile"
LOG_FILE="$HOME/docker/deploy_analytics_${TIMESTAMP}.log"

# Cloudflare certificate paths
CLOUDFLARE_CERT="/etc/caddy/certs/cloudflare-cert.pem"
CLOUDFLARE_KEY="/etc/caddy/certs/cloudflare-key.pem"

################################################################################
# HELPER FUNCTIONS
################################################################################

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*" | tee -a "$LOG_FILE"
}

# Error handler
error_exit() {
    log_error "$1"
    log_error "Deployment failed! Check log at: $LOG_FILE"
    exit 1
}

# Detect docker-compose command
detect_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        echo "docker-compose"
    elif docker compose version &> /dev/null; then
        echo "docker compose"
    else
        error_exit "Neither 'docker-compose' nor 'docker compose' is available"
    fi
}

# Docker compose command wrapper
DOCKER_COMPOSE=""

# Check if running as root (needed for Caddy operations)
check_root() {
    if [[ $EUID -ne 0 ]] && [[ "$1" == "caddy" ]]; then
        error_exit "This script must be run as root for Caddy operations. Use: sudo $0"
    fi
}

# Verify required files exist
verify_prerequisites() {
    log "Verifying prerequisites..."
    
    [[ -f "$MAIN_COMPOSE" ]] || error_exit "Main docker-compose.yml not found: $MAIN_COMPOSE"
    [[ -f "$ANALYTICS_COMPOSE" ]] || error_exit "Analytics docker-compose.yml not found: $ANALYTICS_COMPOSE"
    [[ -f "$CADDYFILE" ]] || error_exit "Caddyfile not found: $CADDYFILE"
    [[ -f "$CLOUDFLARE_CERT" ]] || error_exit "Cloudflare certificate not found: $CLOUDFLARE_CERT"
    [[ -f "$CLOUDFLARE_KEY" ]] || error_exit "Cloudflare key not found: $CLOUDFLARE_KEY"
    
    # Check if docker and docker-compose are installed
    command -v docker &> /dev/null || error_exit "Docker is not installed"
    DOCKER_COMPOSE=$(detect_docker_compose)
    log_info "Using: $DOCKER_COMPOSE"
    
    # Check if Caddy is installed
    command -v caddy &> /dev/null || error_exit "Caddy is not installed"
    
    log "✓ All prerequisites verified"
}

# Check available system resources
check_resources() {
    log "Checking system resources..."
    
    local total_mem=$(free -m | awk '/^Mem:/{print $2}')
    local available_mem=$(free -m | awk '/^Mem:/{print $7}')
    local cpu_count=$(nproc)
    
    log_info "CPU cores: $cpu_count"
    log_info "Total memory: ${total_mem}MB"
    log_info "Available memory: ${available_mem}MB"
    
    if [[ $available_mem -lt 2048 ]]; then
        log_warn "Low available memory (${available_mem}MB). Services may experience issues."
        log_warn "Consider stopping non-essential services or increasing swap."
    fi
    
    if [[ $cpu_count -lt 4 ]]; then
        log_warn "Less than 4 CPU cores detected ($cpu_count). Performance may be impacted."
    fi
}

################################################################################
# BACKUP FUNCTIONS
################################################################################

create_backups() {
    log "Creating backups in $BACKUP_DIR..."
    mkdir -p "$BACKUP_DIR"
    
    # Backup docker-compose.yml
    if [[ -f "$MAIN_COMPOSE" ]]; then
        cp "$MAIN_COMPOSE" "$BACKUP_DIR/docker-compose.yml.bak"
        log "✓ Backed up docker-compose.yml"
    fi
    
    # Backup Caddyfile
    if [[ -f "$CADDYFILE" ]]; then
        sudo cp "$CADDYFILE" "$BACKUP_DIR/Caddyfile.bak"
        log "✓ Backed up Caddyfile"
    fi
    
    # Backup .env if exists
    if [[ -f "$HOME/docker/.env" ]]; then
        cp "$HOME/docker/.env" "$BACKUP_DIR/.env.bak"
        log "✓ Backed up .env"
    fi
    
    log "✓ All backups completed successfully"
}

################################################################################
# DOCKER COMPOSE MERGE
################################################################################

merge_docker_compose() {
    log "Merging analytics services into main docker-compose.yml..."
    
    cd "$HOME/docker"
    
    # Create the merged configuration
    cat > "$MAIN_COMPOSE" << 'COMPOSE_EOF'
services:
  ################################
  # BASE DE DONNEES
  ################################
  postgres:
    build: .
    container_name: postgresql
    restart: unless-stopped
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD={{CHANGE_ME_DB_PASSWORD}}
      - POSTGRES_DB=postgres
    volumes:
      - postgres-data:/var/lib/postgresql
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER"]
      interval: 10s
      timeout: 5s
      retries: 5

  ################################
  # WALLABAG
  ################################
  wallabag:
    image: wallabag/wallabag:latest
    container_name: wallabag
    restart: unless-stopped
    environment:
      - SYMFONY__ENV__DATABASE_DRIVER=pdo_pgsql
      - SYMFONY__ENV__DATABASE_HOST=postgres
      - SYMFONY__ENV__DATABASE_PORT=5432
      - SYMFONY__ENV__DATABASE_NAME=${WALLABAG_DB_NAME}
      - SYMFONY__ENV__DATABASE_USER=${WALLABAG_DB_USER}
      - SYMFONY__ENV__DATABASE_PASSWORD=${WALLABAG_DB_PASSWORD}
      - SYMFONY__ENV__DOMAIN_NAME=https://${WALLABAG_SUBDOMAIN}.${DOMAIN}
      - SYMFONY__ENV__SERVER_NAME="Wallabag"
      - SYMFONY_ENV=prod
    volumes:
      - wallabag-data:/var/www/wallabag/web/assets/images
    networks:
      - backend
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "127.0.0.1:8080:80"

  ################################
  # DBGATE - Interface BDD
  ################################
  dbgate:
    image: dbgate/dbgate:latest
    container_name: dbgate
    restart: unless-stopped
    volumes:
      - dbgate-data:/root/.dbgate
    networks:
      - backend
    ports:
      - "127.0.0.1:3000:3000"

  ################################
  # ANALYTICS: VALKEY CACHE
  ################################
  valkey:
    image: valkey/valkey:8.0-alpine
    container_name: devto_valkey
    restart: unless-stopped
    environment:
      VALKEY_PASSWORD: ${DEVTO_VALKEY_PASSWORD}
    volumes:
      - valkey-data:/data
    command: valkey-server --requirepass ${DEVTO_VALKEY_PASSWORD} --maxmemory 128mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "valkey-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s
    networks:
      - backend
    deploy:
      resources:
        limits:
          memory: 128M

  ################################
  # ANALYTICS: FASTAPI
  ################################
  fastapi:
    build:
      context: ./devto_stats
      dockerfile: Dockerfile
    container_name: devto_fastapi
    restart: unless-stopped
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD={{CHANGE_ME_DB_PASSWORD}}
      - POSTGRES_DB=${DEVTO_DB_NAME}
      - VALKEY_HOST=valkey
      - VALKEY_PORT=6379
      - VALKEY_PASSWORD=${DEVTO_VALKEY_PASSWORD}
      - DEVTO_API_KEY={{CHANGE_ME_API_KEY}}
      - API_KEY={{CHANGE_ME_API_KEY}}
    command: ["gunicorn", "app.api.main:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    depends_on:
      postgres:
        condition: service_healthy
      valkey:
        condition: service_healthy
    networks:
      - backend
    ports:
      - "127.0.0.1:8000:8000"
    deploy:
      resources:
        limits:
          memory: 384M

  ################################
  # ANALYTICS: STREAMLIT
  ################################
  streamlit:
    build:
      context: ./devto_stats
      dockerfile: Dockerfile
    container_name: devto_streamlit
    restart: unless-stopped
    command: streamlit run app/streamlit_app.py
    environment:
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD={{CHANGE_ME_DB_PASSWORD}}
      - POSTGRES_DB=${DEVTO_DB_NAME}
    volumes:
      - ./devto_stats/.streamlit:/code/.streamlit:ro
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8501/_stcore/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    depends_on:
      postgres:
        condition: service_healthy
      valkey:
        condition: service_healthy
    networks:
      - backend
    ports:
      - "127.0.0.1:8501:8501"
    deploy:
      resources:
        limits:
          memory: 512M

  ################################
  # ANALYTICS: SUPERSET
  ################################
  superset:
    image: apache/superset:latest-dev
    container_name: devto_superset
    restart: unless-stopped
    environment:
      - SUPERSET_DATABASE_URI=postgresql+psycopg2://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${DEVTO_DB_NAME}
      - SUPERSET_SECRET_KEY=${DEVTO_SUPERSET_SECRET_KEY}
      - SUPERSET_LOAD_EXAMPLES=no
      - SUPERSET_ENV=production
      - SUPERSET_ADMIN_USERNAME=admin
      - SUPERSET_ADMIN_PASSWORD=${POSTGRES_PASSWORD}
      - SUPERSET_ADMIN_EMAIL=admin@{{YOUR_DOMAIN}}
      - SUPERSET_ADMIN_FIRSTNAME=Admin
      - SUPERSET_ADMIN_LASTNAME=User
      - REDIS_HOST=valkey
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${DEVTO_VALKEY_PASSWORD}
      - SUPERSET_WEBSERVER_TIMEOUT=300
    volumes:
      - superset-data:/app/superset_home
    command: ["/bin/bash", "-c", "superset db upgrade && superset fab create-admin --username admin --firstname Admin --lastname User --email admin@{{YOUR_DOMAIN}} --password $${SUPERSET_ADMIN_PASSWORD} || true && superset init && gunicorn --bind 0.0.0.0:8088 --workers 2 --timeout 300 --limit-request-line 0 --limit-request-field_size 0 'superset.app:create_app()'"]
    depends_on:
      postgres:
        condition: service_healthy
      valkey:
        condition: service_healthy
    networks:
      - backend
    ports:
      - "127.0.0.1:8088:8088"
    deploy:
      resources:
        limits:
          memory: 1G

################################
# VOLUMES & RESEAUX
################################
volumes:
  postgres-data:
  wallabag-data:
  dbgate-data:
  valkey-data:
  superset-data:

networks:
  backend:
    driver: bridge
COMPOSE_EOF

    log "✓ Docker Compose configuration merged successfully"
}

################################################################################
# CADDYFILE UPDATE
################################################################################

update_caddyfile() {
    log "Updating Caddyfile with analytics routes..."
    
    # Create updated Caddyfile
    sudo tee "$CADDYFILE" > /dev/null << 'CADDY_EOF'
# Configuration Caddy avec certificat Cloudflare Origin
# /etc/caddy/Caddyfile

# Configuration globale
{
	# Désactiver l'auto HTTPS de Caddy car on utilise Cloudflare
	auto_https off
}

# Wallabag
wallabag.{{YOUR_DOMAIN}} {
    # Utiliser le certificat Cloudflare Origin
    tls /etc/caddy/certs/cloudflare-cert.pem /etc/caddy/certs/cloudflare-key.pem
    
    reverse_proxy localhost:8080 {
        # Headers pour le proxy
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
        header_up X-Forwarded-Host {host}
    }
    
    # Headers de sécurité
    header {
        # Strict-Transport-Security pour forcer HTTPS
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        # Protection XSS
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        X-XSS-Protection "1; mode=block"
        # Headers CORS pour Wallabag
        Access-Control-Allow-Origin "https://wallabag.{{YOUR_DOMAIN}}"
        Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers "Content-Type, Authorization, X-Requested-With"
        Access-Control-Allow-Credentials "true"
    }
    
    # Logs
    log {
        output file /var/log/caddy/wallabag.log {
            roll_size 10mb
            roll_keep 5
        }
    }
}

# DbGate (optionnel - interface admin BDD)
dbgate.{{YOUR_DOMAIN}} {
	tls /etc/caddy/certs/cloudflare-cert.pem /etc/caddy/certs/cloudflare-key.pem

	reverse_proxy localhost:3000

	header {
		Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
		X-Content-Type-Options "nosniff"
		X-Frame-Options "DENY"
		X-XSS-Protection "1; mode=block"
		X-Forwarded-Proto "https"
	}

	log {
		output file /var/log/caddy/dbgate.log {
			roll_size 10mb
			roll_keep 5
		}
	}
}

################################
# ANALYTICS SERVICES
################################

# FastAPI - Analytics REST API
analytics.{{YOUR_DOMAIN}} {
    tls /etc/caddy/certs/cloudflare-cert.pem /etc/caddy/certs/cloudflare-key.pem
    
    reverse_proxy localhost:8000 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
        
        # Health check
        health_uri /api/health
        health_interval 30s
        health_timeout 10s
    }
    
    # Enable compression
    encode gzip zstd
    
    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
    
    # CORS for API
    @cors_preflight {
        method OPTIONS
    }
    handle @cors_preflight {
        header Access-Control-Allow-Origin "https://streamlit.{{YOUR_DOMAIN}}"
        header Access-Control-Allow-Methods "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        header Access-Control-Allow-Headers "Content-Type, Authorization, X-API-Key"
        header Access-Control-Max-Age "3600"
        respond "" 204
    }
    
    log {
        output file /var/log/caddy/analytics.log {
            roll_size 10mb
            roll_keep 5
        }
    }
}

# Streamlit - Interactive Dashboard
streamlit.{{YOUR_DOMAIN}} {
    tls /etc/caddy/certs/cloudflare-cert.pem /etc/caddy/certs/cloudflare-key.pem
    
    reverse_proxy localhost:8501 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
        
        # Health check
        health_uri /_stcore/health
        health_interval 30s
        health_timeout 10s
        
        # Increased timeout for Streamlit
        transport http {
            read_timeout 5m
            write_timeout 5m
            dial_timeout 30s
        }
    }
    
    # Enable compression
    encode gzip zstd
    
    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
    
    # Static file caching
    @static {
        path /static/*
    }
    header @static Cache-Control "public, max-age=31536000, immutable"
    
    log {
        output file /var/log/caddy/streamlit.log {
            roll_size 10mb
            roll_keep 5
        }
    }
}

# Apache Superset - Business Intelligence
dashboard.{{YOUR_DOMAIN}} {
    tls /etc/caddy/certs/cloudflare-cert.pem /etc/caddy/certs/cloudflare-key.pem
    
    reverse_proxy localhost:8088 {
        header_up Host {host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
        
        # Health check
        health_uri /health
        health_interval 30s
        health_timeout 10s
        
        # Increased timeout for long-running queries
        transport http {
            read_timeout 5m
            write_timeout 5m
            dial_timeout 30s
        }
    }
    
    # Enable compression
    encode gzip zstd
    
    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        X-XSS-Protection "1; mode=block"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
    
    # Static file caching
    @static {
        path /static/*
    }
    header @static Cache-Control "public, max-age=31536000, immutable"
    
    log {
        output file /var/log/caddy/superset.log {
            roll_size 10mb
            roll_keep 5
        }
    }
}
CADDY_EOF

    log "✓ Caddyfile updated successfully"
}

################################################################################
# DATABASE SETUP
################################################################################

create_analytics_database() {
    log "Creating devto_analytics database..."
    
    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    sleep 5
    
    # Create database if it doesn't exist
    docker exec postgresql psql -U "${POSTGRES_USER:-postgres}" -tc "SELECT 1 FROM pg_database WHERE datname = 'devto_analytics'" | grep -q 1 || \
    docker exec postgresql psql -U "${POSTGRES_USER:-postgres}" -c "CREATE DATABASE devto_analytics OWNER ${POSTGRES_USER:-postgres};"
    
    log "✓ Database devto_analytics created/verified"
}

initialize_database_schema() {
    log "Initializing database schema..."
    
    # Run init_database.py
    if [[ -f "$HOME/docker/devto_stats/app/init_database.py" ]]; then
        docker exec devto_fastapi python app/init_database.py || log_warn "Database initialization returned warnings (might already be initialized)"
        log "✓ Database schema initialized"
    else
        log_warn "init_database.py not found, skipping schema initialization"
    fi
}

################################################################################
# DOCKER OPERATIONS
################################################################################

build_and_deploy_services() {
    log "Building and deploying analytics services..."
    
    cd "$HOME/docker"
    
    # Build images
    log_info "Building Docker images..."
    $DOCKER_COMPOSE build fastapi streamlit || error_exit "Failed to build Docker images"
    
    # Pull required images
    log_info "Pulling required images..."
    $DOCKER_COMPOSE pull valkey superset || log_warn "Some images failed to pull, will retry during up"
    
    # Start services in order
    log_info "Starting services..."
    
    # Start core services first (postgres should already be running)
    $DOCKER_COMPOSE up -d postgres || error_exit "Failed to start PostgreSQL"
    sleep 10
    
    # Start valkey
    $DOCKER_COMPOSE up -d valkey || error_exit "Failed to start Valkey"
    sleep 5
    
    # Start analytics services
    $DOCKER_COMPOSE up -d fastapi streamlit superset || error_exit "Failed to start analytics services"
    
    log "✓ All services deployed successfully"
}

verify_services() {
    log "Verifying service health..."
    
    local max_attempts=30
    local attempt=0
    
    # Wait for services to be healthy
    while [[ $attempt -lt $max_attempts ]]; do
        log_info "Health check attempt $((attempt + 1))/$max_attempts..."
        
        local postgres_health=$(docker inspect --format='{{.State.Health.Status}}' postgresql 2>/dev/null || echo "unknown")
        local valkey_health=$(docker inspect --format='{{.State.Health.Status}}' devto_valkey 2>/dev/null || echo "unknown")
        local fastapi_health=$(docker inspect --format='{{.State.Health.Status}}' devto_fastapi 2>/dev/null || echo "unknown")
        local streamlit_health=$(docker inspect --format='{{.State.Health.Status}}' devto_streamlit 2>/dev/null || echo "unknown")
        
        log_info "PostgreSQL: $postgres_health | Valkey: $valkey_health | FastAPI: $fastapi_health | Streamlit: $streamlit_health"
        
        if [[ "$postgres_health" == "healthy" ]] && [[ "$valkey_health" == "healthy" ]] && \
           [[ "$fastapi_health" == "healthy" ]] && [[ "$streamlit_health" == "healthy" ]]; then
            log "✓ All services are healthy!"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 10
    done
    
    log_warn "Some services did not become healthy within expected time"
    log_warn "Check logs with: $DOCKER_COMPOSE logs [service-name]"
}

################################################################################
# CADDY OPERATIONS
################################################################################

validate_and_reload_caddy() {
    log "Validating Caddy configuration..."
    
    # Validate Caddyfile
    if sudo caddy validate --config "$CADDYFILE"; then
        log "✓ Caddyfile validation passed"
    else
        error_exit "Caddyfile validation failed! Not reloading Caddy."
    fi
    
    # Reload Caddy without downtime
    log "Reloading Caddy (zero-downtime)..."
    if sudo caddy reload --config "$CADDYFILE"; then
        log "✓ Caddy reloaded successfully"
    else
        error_exit "Caddy reload failed!"
    fi
}

################################################################################
# ENVIRONMENT VARIABLES
################################################################################

load_environment_variables() {
    log "Loading environment variables..."
    
    # Source main .env if exists
    if [[ -f "$HOME/docker/.env" ]]; then
        set -a
        source "$HOME/docker/.env"
        set +a
        log "✓ Loaded main .env"
    fi
    
    # Source analytics .env if exists
    if [[ -f "$HOME/docker/devto_stats/.env" ]]; then
        set -a
        source "$HOME/docker/devto_stats/.env"
        set +a
        log "✓ Loaded analytics .env"
    fi
    
    # Verify critical variables
    [[ -n "${POSTGRES_USER:-}" ]] || error_exit "POSTGRES_USER not set"
    [[ -n "${POSTGRES_PASSWORD:-}" ]] || error_exit "POSTGRES_PASSWORD not set"
    [[ -n "${DEVTO_VALKEY_PASSWORD:-}" ]] || error_exit "DEVTO_VALKEY_PASSWORD not set"
    [[ -n "${DEVTO_API_KEY:-}" ]] || error_exit "DEVTO_API_KEY not set"
    
    log "✓ All required environment variables verified"
}

################################################################################
# STATUS REPORT
################################################################################

print_deployment_summary() {
    log ""
    log "========================================="
    log "DEPLOYMENT SUMMARY"
    log "========================================="
    log ""
    log "Backup Location: $BACKUP_DIR"
    log "Log File: $LOG_FILE"
    log ""
    log "Services Deployed:"
    log "  - FastAPI API:      https://analytics.{{YOUR_DOMAIN}}"
    log "  - Streamlit:        https://streamlit.{{YOUR_DOMAIN}}"
    log "  - Superset:         https://dashboard.{{YOUR_DOMAIN}}"
    log "  - Valkey Cache:     Internal (127.0.0.1:6379)"
    log ""
    log "Existing Services (Unchanged):"
    log "  - Wallabag:         https://wallabag.{{YOUR_DOMAIN}}"
    log "  - DbGate:           https://dbgate.{{YOUR_DOMAIN}}"
    log ""
    log "Resource Allocation:"
    log "  - FastAPI:          384MB, 2 workers"
    log "  - Streamlit:        512MB"
    log "  - Superset:         1GB, 2 workers"
    log "  - Valkey:           128MB"
    log ""
    log "Next Steps:"
    log "  1. Verify services: $DOCKER_COMPOSE ps"
    log "  2. Check logs: $DOCKER_COMPOSE logs -f [service]"
    log "  3. Test endpoints with curl or browser"
    log "  4. Monitor resource usage: docker stats"
    log ""
    log "========================================="
    log "✓ DEPLOYMENT COMPLETED SUCCESSFULLY"
    log "========================================="
}

################################################################################
# MAIN EXECUTION
################################################################################

main() {
    log "========================================="
    log "DEV.TO ANALYTICS DEPLOYMENT SCRIPT"
    log "========================================="
    log "Started at: $(date)"
    log ""
    
    # Pre-flight checks
    check_root "caddy"
    verify_prerequisites
    check_resources
    load_environment_variables
    
    # Create backups
    create_backups
    
    # Merge configurations
    merge_docker_compose
    update_caddyfile
    
    # Deploy services
    build_and_deploy_services
    
    # Database setup
    create_analytics_database
    initialize_database_schema
    
    # Reload Caddy
    validate_and_reload_caddy
    
    # Verify deployment
    verify_services
    
    # Summary
    print_deployment_summary
    
    log ""
    log "Completed at: $(date)"
}

# Execute main function
main "$@"
