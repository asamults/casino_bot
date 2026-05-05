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
