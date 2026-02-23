.PHONY: help install lint typecheck test check \
       db-up db-down db-migrate db-reset \
       docker-test docker-migration docker-monitoring docker-backtest docker-down \
       clean

SHELL := /bin/bash
DB_URL ?= postgresql+asyncpg://jamlechtrader:jamlechtrader@localhost:5436/jamlechtrader

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Local development ──────────────────────────────────────────────

install: ## Install all dependencies (dev + extras)
	uv sync --frozen --group dev

lint: ## Run ruff linter
	uv run ruff check .

typecheck: ## Run mypy type checker
	uv run mypy jamlechtrader/

test: ## Run pytest
	uv run pytest tests/ -v

check: lint typecheck test ## Run lint + typecheck + tests

# ── Database (local PostgreSQL via Docker) ─────────────────────────

db-up: ## Start PostgreSQL container
	docker compose up -d postgres
	@echo "Waiting for PostgreSQL on port 5436..."
	@until docker compose exec postgres pg_isready -U jamlechtrader -p 5436 -q 2>/dev/null; do sleep 1; done
	@echo "PostgreSQL is ready."

db-down: ## Stop PostgreSQL container
	docker compose down postgres

db-migrate: ## Run alembic migrations against local DB
	DATABASE_URL=$(DB_URL) uv run alembic upgrade head

db-reset: ## Drop and recreate database (destructive)
	docker compose down postgres -v
	$(MAKE) db-up
	$(MAKE) db-migrate

# ── Docker: testing pipeline ───────────────────────────────────────

docker-test: ## Run full CI pipeline in Docker (lint + typecheck + tests + migrations)
	docker compose -f docker-compose.test.yml --profile all up --build --abort-on-container-exit --exit-code-from test-runner
	docker compose -f docker-compose.test.yml --profile all down -v

docker-migration: ## Run only DB migration validation in Docker
	docker compose -f docker-compose.test.yml --profile migration up --build --abort-on-container-exit --exit-code-from migrations
	docker compose -f docker-compose.test.yml --profile migration down -v

# ── Docker: services ───────────────────────────────────────────────

docker-monitoring: ## Start dashboard + Prometheus + Grafana
	docker compose --profile monitoring up -d --build
	@echo ""
	@echo "Dashboard:  http://localhost:8050"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana:    http://localhost:3000  (admin/admin)"

docker-backtest: ## Run a backtest in Docker
	docker compose --profile backtest up --build --abort-on-container-exit
	docker compose --profile backtest down

docker-down: ## Stop all Docker services and remove volumes
	docker compose --profile monitoring --profile backtest --profile paper down -v
	docker compose -f docker-compose.test.yml --profile all --profile migration down -v

# ── Cleanup ────────────────────────────────────────────────────────

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .hypothesis .benchmarks
	rm -rf build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
