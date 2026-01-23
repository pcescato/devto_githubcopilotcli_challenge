.PHONY: help up down restart logs ps clean init-db backup restore test

# Color output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

help: ## Show this help message
	@echo "$(CYAN)DEV.to Analytics - Docker Management$(RESET)"
	@echo ""
	@echo "$(GREEN)Available commands:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(CYAN)%-20s$(RESET) %s\n", $$1, $$2}'

# Docker Compose commands
up: ## Start all services
	@echo "$(GREEN)Starting all services...$(RESET)"
	docker-compose up -d
	@echo "$(GREEN)Services started!$(RESET)"
	@make status

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(RESET)"
	docker-compose down
	@echo "$(YELLOW)Services stopped!$(RESET)"

restart: ## Restart all services
	@echo "$(YELLOW)Restarting all services...$(RESET)"
	docker-compose restart
	@echo "$(GREEN)Services restarted!$(RESET)"

logs: ## View logs from all services
	docker-compose logs -f

logs-postgres: ## View PostgreSQL logs
	docker-compose logs -f postgres

logs-valkey: ## View Valkey logs
	docker-compose logs -f valkey

logs-superset: ## View Superset logs
	docker-compose logs -f superset

logs-dbgate: ## View DbGate logs
	docker-compose logs -f dbgate

ps: ## Show running containers
	docker-compose ps

status: ## Show service status with health checks
	@echo "$(CYAN)Service Status:$(RESET)"
	@docker-compose ps --format "table {{.Service}}\t{{.Status}}\t{{.Ports}}"

# Database commands
init-db: ## Initialize database schema
	@echo "$(GREEN)Initializing database schema...$(RESET)"
	cd app && python3 init_database.py
	@echo "$(GREEN)Database initialized!$(RESET)"

validate-db: ## Validate database schema
	@echo "$(CYAN)Validating database schema...$(RESET)"
	cd app && python3 validate_schema.py

psql: ## Connect to PostgreSQL
	docker-compose exec postgres psql -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2)

db-stats: ## Show database statistics
	docker-compose exec postgres psql -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2) -c "SELECT * FROM devto_analytics.get_db_stats();"

db-size: ## Show table sizes
	docker-compose exec postgres psql -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2) -c "SELECT * FROM devto_analytics.get_table_sizes();"

backup: ## Create database backup
	@echo "$(CYAN)Creating database backup...$(RESET)"
	@mkdir -p backups
	docker-compose exec postgres pg_dump -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) $(shell grep POSTGRES_DB .env | cut -d '=' -f2) > backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)Backup created in backups/$(RESET)"

restore: ## Restore database from backup (BACKUP_FILE=backups/backup.sql)
	@echo "$(YELLOW)Restoring database from $(BACKUP_FILE)...$(RESET)"
	@if [ -z "$(BACKUP_FILE)" ]; then echo "$(RED)Error: BACKUP_FILE not specified$(RESET)"; exit 1; fi
	docker-compose exec -T postgres psql -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) -d $(shell grep POSTGRES_DB .env | cut -d '=' -f2) < $(BACKUP_FILE)
	@echo "$(GREEN)Database restored!$(RESET)"

# Cache commands
valkey-cli: ## Connect to Valkey CLI
	docker-compose exec valkey valkey-cli -a $(shell grep VALKEY_PASSWORD .env | cut -d '=' -f2)

valkey-stats: ## Show Valkey statistics
	docker-compose exec valkey valkey-cli -a $(shell grep VALKEY_PASSWORD .env | cut -d '=' -f2) INFO stats

valkey-flush: ## Flush Valkey cache (WARNING: clears all data)
	@echo "$(RED)WARNING: This will clear ALL cached data!$(RESET)"
	@read -p "Are you sure? [y/N]: " confirm && [ "$$confirm" = "y" ] && \
		docker-compose exec valkey valkey-cli -a $(shell grep VALKEY_PASSWORD .env | cut -d '=' -f2) FLUSHALL && \
		echo "$(GREEN)Cache flushed!$(RESET)" || echo "$(YELLOW)Cancelled$(RESET)"

# Service-specific commands
superset-init: ## Reinitialize Superset
	@echo "$(CYAN)Reinitializing Superset...$(RESET)"
	docker-compose exec superset /app/docker/init-superset.sh
	@echo "$(GREEN)Superset reinitialized!$(RESET)"

superset-create-admin: ## Create new Superset admin user
	docker-compose exec superset superset fab create-admin

dbgate-open: ## Open DbGate in browser
	@echo "$(CYAN)Opening DbGate...$(RESET)"
	@open http://localhost:3000 2>/dev/null || xdg-open http://localhost:3000 2>/dev/null || echo "Open http://localhost:3000 in your browser"

superset-open: ## Open Superset in browser
	@echo "$(CYAN)Opening Superset...$(RESET)"
	@open http://localhost:8088 2>/dev/null || xdg-open http://localhost:8088 2>/dev/null || echo "Open http://localhost:8088 in your browser"

# Cleanup commands
clean: ## Remove all containers and volumes (WARNING: data loss)
	@echo "$(RED)WARNING: This will remove all data!$(RESET)"
	@read -p "Are you sure? [y/N]: " confirm && [ "$$confirm" = "y" ] && \
		docker-compose down -v && \
		echo "$(GREEN)Cleanup complete!$(RESET)" || echo "$(YELLOW)Cancelled$(RESET)"

clean-logs: ## Clean up log files
	@echo "$(YELLOW)Cleaning log files...$(RESET)"
	find . -name "*.log" -type f -delete
	@echo "$(GREEN)Log files cleaned!$(RESET)"

prune: ## Remove unused Docker resources
	@echo "$(YELLOW)Pruning unused Docker resources...$(RESET)"
	docker system prune -f
	@echo "$(GREEN)Prune complete!$(RESET)"

# Setup commands
setup: ## Initial setup (copy .env, start services)
	@echo "$(CYAN)Setting up DEV.to Analytics...$(RESET)"
	@if [ ! -f .env ]; then \
		cp .env.example .env && \
		echo "$(GREEN).env file created. Please update with your credentials.$(RESET)"; \
	else \
		echo "$(YELLOW).env file already exists$(RESET)"; \
	fi
	@echo "$(CYAN)Starting services...$(RESET)"
	@make up
	@echo "$(CYAN)Waiting for services to be ready...$(RESET)"
	@sleep 10
	@echo "$(CYAN)Initializing database...$(RESET)"
	@make init-db
	@echo ""
	@echo "$(GREEN)Setup complete!$(RESET)"
	@echo ""
	@echo "$(CYAN)Access points:$(RESET)"
	@echo "  PostgreSQL: localhost:5432"
	@echo "  DbGate:     http://localhost:3000"
	@echo "  Superset:   http://localhost:8088"
	@echo ""

install-deps: ## Install Python dependencies
	@echo "$(CYAN)Installing Python dependencies...$(RESET)"
	cd app && pip install -r requirements.txt
	@echo "$(GREEN)Dependencies installed!$(RESET)"

# Testing commands
test-connection: ## Test database connection
	@echo "$(CYAN)Testing PostgreSQL connection...$(RESET)"
	@docker-compose exec postgres pg_isready -U $(shell grep POSTGRES_USER .env | cut -d '=' -f2) && \
		echo "$(GREEN)PostgreSQL: OK$(RESET)" || echo "$(RED)PostgreSQL: FAILED$(RESET)"
	@echo "$(CYAN)Testing Valkey connection...$(RESET)"
	@docker-compose exec valkey valkey-cli -a $(shell grep VALKEY_PASSWORD .env | cut -d '=' -f2) PING > /dev/null && \
		echo "$(GREEN)Valkey: OK$(RESET)" || echo "$(RED)Valkey: FAILED$(RESET)"

health: ## Check health of all services
	@echo "$(CYAN)Health Check:$(RESET)"
	@docker inspect devto_postgres --format='PostgreSQL: {{.State.Health.Status}}' 2>/dev/null || echo "PostgreSQL: $(RED)not running$(RESET)"
	@docker inspect devto_valkey --format='Valkey: {{.State.Health.Status}}' 2>/dev/null || echo "Valkey: $(RED)not running$(RESET)"
	@docker inspect devto_superset --format='Superset: {{.State.Status}}' 2>/dev/null || echo "Superset: $(RED)not running$(RESET)"
	@docker inspect devto_dbgate --format='DbGate: {{.State.Status}}' 2>/dev/null || echo "DbGate: $(RED)not running$(RESET)"

# Monitoring commands
monitor: ## Monitor resource usage
	@echo "$(CYAN)Monitoring resource usage (Ctrl+C to exit)...$(RESET)"
	@watch -n 2 'docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"'

# Documentation
docs: ## View documentation
	@echo "$(CYAN)Documentation files:$(RESET)"
	@echo "  README.md              - Main documentation"
	@echo "  docker/README.md       - Docker infrastructure guide"
	@echo "  app/INSTALL.md         - Installation guide"
	@echo "  app/MIGRATION_SUMMARY.md - Migration details"

# Development
dev: ## Start services in development mode
	@echo "$(CYAN)Starting in development mode...$(RESET)"
	docker-compose up

# Default target
.DEFAULT_GOAL := help
