# Arash External API Service - Makefile

.PHONY: help install run run-dev test lint format clean \
        migrate-up migrate-down migrate-status migrate-create \
        db-channels db-keys db-channel-create db-key-create

UV ?= $(shell which uv 2>/dev/null)

help:
	@echo "Arash External API v1.0"
	@echo ""
	@echo "Development:"
	@echo "  make install     Install dependencies"
	@echo "  make run         Start service (production)"
	@echo "  make run-dev     Start with auto-reload"
	@echo "  make lint        Check code quality (ruff)"
	@echo "  make format      Format code (black)"
	@echo "  make clean       Remove cache"
	@echo ""
	@echo "Database:"
	@echo "  make migrate-up           Apply migrations"
	@echo "  make migrate-down         Rollback"
	@echo "  make migrate-status       Show status"
	@echo "  make migrate-create MSG=\"description\""
	@echo ""
	@echo "Channels:"
	@echo "  make db-channels          List channels"
	@echo "  make db-keys              List API keys"
	@echo "  make db-channel-create NAME=\"Ch\" [DAILY=100] [MONTHLY=3000]"
	@echo "  make db-key-create CHANNEL=<id> NAME=\"Key\""
	@echo ""

# Development
install:
	@command -v $(UV) >/dev/null || (echo "ERROR: uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh" && exit 1)
	$(UV) sync --all-extras

run:
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 3000

run-dev:
	$(UV) run uvicorn app.main:app --host 0.0.0.0 --port 3000 --reload

test:
	@echo "No tests available. Tests directory was removed."
	@exit 1

lint:
	$(UV) run ruff check app/

format:
	$(UV) run black app/

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete

# Database Migrations
migrate-up:
	$(UV) run alembic upgrade head

migrate-down:
	$(UV) run alembic downgrade -1

migrate-status:
	@$(UV) run alembic current
	@echo ""
	@$(UV) run alembic history

migrate-create:
ifndef MSG
	@echo "ERROR: MSG required. Usage: make migrate-create MSG=\"description\""
	@exit 1
endif
	$(UV) run alembic revision --autogenerate -m "$(MSG)"

# Channel & API Key Management
db-channels:
	@$(UV) run python scripts/manage_api_keys.py channel list

db-keys:
	@$(UV) run python scripts/manage_api_keys.py key list

db-channel-create:
ifndef NAME
	@echo "ERROR: NAME required. Usage: make db-channel-create NAME=\"Channel\" [DAILY=100] [MONTHLY=3000]"
	@exit 1
endif
	$(UV) run python scripts/manage_api_keys.py channel create "$(NAME)" \
		$(if $(DAILY),--daily-quota $(DAILY)) \
		$(if $(MONTHLY),--monthly-quota $(MONTHLY))

db-key-create:
ifndef CHANNEL
	@echo "ERROR: CHANNEL required. Usage: make db-key-create CHANNEL=<id> NAME=\"Key\""
	@exit 1
endif
ifndef NAME
	@echo "ERROR: NAME required. Usage: make db-key-create CHANNEL=<id> NAME=\"Key\""
	@exit 1
endif
	$(UV) run python scripts/manage_api_keys.py key create $(CHANNEL) "$(NAME)"
