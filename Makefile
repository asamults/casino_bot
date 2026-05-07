# Makefile for the casino_bot project

# Docker image name
IMAGE_NAME = casino-bot:dev

# Ports
API_PORT = 8000
DB_PORT  = 5432

# Local CI-style checks (requires venv with dev tools: ruff, bandit, pip-audit)
ci-check:
	ruff check .
	ruff format --check .
	pytest -q
	bandit -r src -ll
	pip-audit --progress-spinner off

# GameDay drills (M3W3)
drill-smoke:
	./scripts/drill/smoke.sh

drill-db-down:
	./scripts/drill/drill_db_down.sh

drill-5xx-spike:
	./scripts/drill/drill_5xx_spike.sh

drill-webhook-dead-letter:
	./scripts/drill/drill_webhook_dead_letter.sh

# Soak (M4W2)
soak-prod:
	./scripts/soak/run_soak_prod_compose.sh

# Production cutover readiness (dry-run)
prod-preflight:
	./scripts/ops/production_preflight.sh

# Backup/restore rehearsal (M5W1)
pg-backup-compose:
	./scripts/ops/pg_dump_compose.sh

pg-restore-compose:
	./scripts/ops/pg_restore_compose.sh

pg-verify-compose:
	./scripts/ops/pg_verify_compose.sh

staging-up:
	docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build

staging-down:
	docker compose --env-file .env.staging -f docker-compose.staging.yml down

# Build Docker image
build:
	docker build -t $(IMAGE_NAME) .

# Run containers (foreground)
up:
	docker compose up --build

# Run containers in detached mode
up-detached:
	docker compose up -d --build

# Stop and remove containers
down:
	docker compose down

# Restart API without rebuilding the image
restart-api:
	docker compose restart api

# Follow logs for all services
logs:
	docker compose logs -f

# Follow API logs
logs-api:
	docker compose logs -f api

# Follow Postgres logs
logs-db:
	docker compose logs -f postgres

# Remove unused Docker objects
prune:
	docker system prune -af
	docker volume prune -f

# Run API container only (no Postgres; for debugging)
run-api:
	docker run --rm -p $(API_PORT):$(API_PORT) $(IMAGE_NAME)
