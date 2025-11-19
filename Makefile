# Arash External API Service - Makefile
# Essential commands for development and deployment (using uv)

.PHONY: help check-uv install run run-dev test lint format clean \
        migrate-up migrate-down migrate-status migrate-create \
        db-teams db-keys db-team-create db-key-create demo-logging show-config

# Detect uv location (allow override with UV=/path/to/uv)
UV ?= $(shell which uv 2>/dev/null)

# Check if uv is available
check-uv:
	@if ! command -v $(UV) >/dev/null 2>&1; then \
		echo "[ERROR] uv not found!"; \
		echo ""; \
		echo "Please install uv:"; \
		echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		echo ""; \
		echo "Or override uv location:"; \
		echo "  make test UV=/path/to/uv"; \
		exit 1; \
	fi

# Default target
help:
	@echo "========================================================================"
	@echo "Arash External API Service v1.1 - Essential Commands"
	@echo "========================================================================"
	@echo ""
	@echo "Package Manager: uv ($(UV))"
	@echo ""
	@echo "[Development]"
	@echo "  make install        Install dependencies"
	@echo "  make run            Run application (port 3000)"
	@echo "  make run-dev        Run with auto-reload (development)"
	@echo "  make test           Run test suite"
	@echo "  make lint           Check code quality (ruff)"
	@echo "  make format         Format code (black)"
	@echo "  make clean          Remove cache files"
	@echo "  make show-config    Show current configuration"
	@echo ""
	@echo "[Database Migrations]"
	@echo "  make migrate-up        Apply pending migrations"
	@echo "  make migrate-down      Rollback last migration"
	@echo "  make migrate-status    Show migration status"
	@echo "  make migrate-create    Create new migration"
	@echo ""
	@echo "[Team & API Key Management]"
	@echo "  make db-teams          List all teams"
	@echo "  make db-keys           List all API keys"
	@echo "  make db-team-create    Create team: NAME=\"Team\" [DAILY=100] [MONTHLY=3000]"
	@echo "  make db-key-create     Create API key: TEAM=<id> NAME=\"Key\" [LEVEL=user]"
	@echo ""
	@echo "[Logging]"
	@echo "  make demo-logging   Run logging demo (timestamp modes)"
	@echo ""
	@echo "For full documentation, see README.md"
	@echo ""

# ============================================================================
# Development
# ============================================================================

install: check-uv
	@echo "[Installing dependencies with uv...]"
	$(UV) sync --all-extras

run: check-uv
	@echo "[Starting Arash API Service...]"
	@echo "API: http://localhost:3000"
	@echo "Docs: http://localhost:3000/docs"
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 3000

run-dev: check-uv
	@echo "[Starting Arash API Service (Development Mode)...]"
	@echo "API: http://localhost:3000"
	@echo "Docs: http://localhost:3000/docs"
	@echo "Auto-reload: Enabled"
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload

test: check-uv
	@echo "[Running tests...]"
	$(UV) run pytest -v

lint: check-uv
	@echo "[Checking code quality...]"
	$(UV) run ruff check app/ tests/

format: check-uv
	@echo "[Formatting code...]"
	$(UV) run black app/ tests/

clean:
	@echo "[Cleaning cache...]"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "[OK] Cache cleaned"

show-config: check-uv
	@echo "[Current Configuration]"
	@echo "Environment: $$(grep '^ENVIRONMENT=' .env | cut -d'=' -f2)"
	@echo "Log Level: $$(grep '^LOG_LEVEL=' .env | cut -d'=' -f2)"
	@echo "Log Timestamp: $$(grep '^LOG_TIMESTAMP=' .env | cut -d'=' -f2)"
	@echo "API Docs: $$(grep '^ENABLE_API_DOCS=' .env | cut -d'=' -f2)"
	@echo "Database: $$(grep '^DB_NAME=' .env | cut -d'=' -f2)"
	@echo "DB Host: $$(grep '^DB_HOST=' .env | cut -d'=' -f2)"

demo-logging:
	@echo "[Running Logging Demo...]"
	python3 demo_timestamp_modes.py

# ============================================================================
# Database Migrations
# ============================================================================

migrate-up: check-uv
	@echo "[Applying migrations...]"
	$(UV) run alembic upgrade head
	@echo "[OK] Migrations applied"

migrate-down: check-uv
	@echo "[Rolling back last migration...]"
	$(UV) run alembic downgrade -1
	@echo "[OK] Migration rolled back"

migrate-status: check-uv
	@echo "[Migration Status]"
	@$(UV) run alembic current
	@echo ""
	@echo "[Migration History]"
	@$(UV) run alembic history

migrate-create: check-uv
ifndef MSG
	@echo "[ERROR] MSG is required"
	@echo "Usage: make migrate-create MSG=\"Description of migration\""
	@exit 1
endif
	@echo "[Creating new migration: $(MSG)]"
	$(UV) run alembic revision --autogenerate -m "$(MSG)"
	@echo "[OK] Migration created"

# ============================================================================
# Team & API Key Management
# ============================================================================

db-teams: check-uv
	@$(UV) run python scripts/manage_api_keys.py team list

db-keys: check-uv
	@$(UV) run python scripts/manage_api_keys.py key list

db-team-create: check-uv
ifndef NAME
	@echo "[ERROR] NAME is required"
	@echo "Usage: make db-team-create NAME=\"Team\" [DAILY=100] [MONTHLY=3000]"
	@exit 1
endif
	$(UV) run python scripts/manage_api_keys.py team create "$(NAME)" \
		$(if $(DAILY),--daily-quota $(DAILY)) \
		$(if $(MONTHLY),--monthly-quota $(MONTHLY))

db-key-create: check-uv
ifndef TEAM
	@echo "[ERROR] TEAM and NAME are required"
	@echo "Usage: make db-key-create TEAM=<id> NAME=\"Key\" [LEVEL=user]"
	@exit 1
endif
ifndef NAME
	@echo "[ERROR] NAME is required"
	@echo "Usage: make db-key-create TEAM=<id> NAME=\"Key\" [LEVEL=user]"
	@exit 1
endif
	$(UV) run python scripts/manage_api_keys.py key create $(TEAM) "$(NAME)" \
		$(if $(LEVEL),--level $(LEVEL))
