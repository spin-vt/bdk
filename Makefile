# BDK developer commands. Run `make` or `make help` to list them.
.DEFAULT_GOAL := help
COMPOSE := docker compose
TEST_COMPOSE := docker compose -f docker-compose.test.yml
SMOKE_COMPOSE := docker compose -f docker-compose.smoke.yml

.PHONY: help up up-build down logs ps shell test lint fmt seed grant-admin smoke migrate migration

help: ## List available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start the full dev stack (needs a .env — copy .env.example)
	$(COMPOSE) up

up-build: ## Rebuild images and start the dev stack
	$(COMPOSE) up --build

down: ## Stop the dev stack
	$(COMPOSE) down

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

ps: ## Show running services
	$(COMPOSE) ps

shell: ## Open a shell in the backend container
	$(COMPOSE) exec backend sh

test: ## Run the committable test suite in Docker (golden tests deselected)
	$(TEST_COMPOSE) run --rm test

smoke: ## Boot the real backend image (gunicorn + redis + alembic) and health-check /api
	@$(SMOKE_COMPOSE) up --build --wait --wait-timeout 240; status=$$?; \
	$(SMOKE_COMPOSE) logs --no-color smoke-backend | tail -n 30; \
	$(SMOKE_COMPOSE) down -v >/dev/null 2>&1; \
	exit $$status

lint: ## Run ruff (lint) in Docker
	$(TEST_COMPOSE) run --rm --no-deps test sh -c "uv sync --frozen && uv run ruff check . && uv run ruff format --check ."

fmt: ## Apply ruff formatting in Docker
	$(TEST_COMPOSE) run --rm --no-deps test sh -c "uv sync --frozen && uv run ruff format ."

seed: ## Seed a dev org + verified user + sample filing (stack must be up)
	$(COMPOSE) exec -e PYTHONPATH=/app backend python scripts/seed.py

grant-admin: ## Grant platform-admin to a user:  make grant-admin email=you@example.com
	$(COMPOSE) exec -e PYTHONPATH=/app backend python scripts/grant_platform_admin.py $(email)

migrate: ## Apply DB migrations (alembic upgrade head)
	$(COMPOSE) exec backend alembic upgrade head

migration: ## Create a migration:  make migration m="add foo table"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

restart-app: ## Restart backend + worker (worker preloads task code). ⚠ Kills any RUNNING job mid-flight (stuck "updating…" until the sweep) — check the job pill first
	@active=$$(docker compose exec db psql -tA -U $${POSTGRES_USER:-$$(grep ^POSTGRES_USER .env | cut -d= -f2)} -d $$(grep ^POSTGRES_DB .env | cut -d= -f2) -c "select count(*) from celerytaskinfo where status in ('PENDING','STARTED','RETRY')" 2>/dev/null || echo 0); \
	if [ "$$active" != "0" ]; then echo "⚠  $$active job(s) still running — restarting will kill them. Ctrl-C to abort, or wait..."; sleep 5; fi
	docker compose restart backend work
