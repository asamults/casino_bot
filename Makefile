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

# Off-host encrypted backup + isolated restore (M5W2)
# Usage:
#   make backup-offhost BACKUP_DEST=/var/tmp/casino_bot_offhost/
#   make backup-offhost BACKUP_DEST=user@host:/var/backups/casino_bot/ SSH_OPTS="-i ~/.ssh/id_ed25519"
backup-offhost:
	./scripts/ops/pg_backup_encrypt.sh
	@latest=$$(ls -1t backups/*.dump.age backups/*.dump.gpg 2>/dev/null | head -n1); \
	  if [ -z "$$latest" ]; then echo "FAIL: no encrypted backup found in backups/"; exit 2; fi; \
	  if [ -z "$(BACKUP_DEST)" ]; then echo "FAIL: BACKUP_DEST not set"; exit 2; fi; \
	  BACKUP_FILE=$$latest BACKUP_DEST=$(BACKUP_DEST) SSH_OPTS="$(SSH_OPTS)" ./scripts/ops/backup_offhost_copy.sh

# Usage:
#   make restore-isolated BACKUP_FILE=./backups/<file>.dump.age \
#                         AGE_IDENTITY_FILE=$$HOME/.config/casino_bot/age-identity.txt
restore-isolated:
	@if [ -z "$(BACKUP_FILE)" ]; then echo "FAIL: BACKUP_FILE not set"; exit 2; fi
	BACKUP_FILE=$(BACKUP_FILE) \
	  AGE_IDENTITY_FILE="$${AGE_IDENTITY_FILE}" \
	  GPG_PASSPHRASE_FILE="$${GPG_PASSPHRASE_FILE}" \
	  ENV_FILE="$${ENV_FILE:-.env.restore.example}" \
	  HOST_HEADER="$${HOST_HEADER:-api.example.com}" \
	  KEEP_STACK="$${KEEP_STACK:-false}" \
	  ./scripts/ops/restore_isolated_compose.sh

# Re-run only the probe verification against an existing isolated api container.
# Usage:
#   make verify-restore-isolated API_CONTAINER=casino_bot_restore_<UTC>-api-1
verify-restore-isolated:
	@if [ -z "$(API_CONTAINER)" ]; then echo "FAIL: API_CONTAINER not set"; exit 2; fi
	API_CONTAINER=$(API_CONTAINER) \
	  HOST_HEADER="$${HOST_HEADER:-api.example.com}" \
	  COMPOSE_FILE=docker-compose.restore.yml \
	  ENV_FILE="$${ENV_FILE:-.env.restore.example}" \
	  ./scripts/ops/pg_verify_compose.sh

# One command: backup → encrypt → copy (local DEST) → isolated restore → probes PASS/FAIL.
# Requires: age, docker, ops/backup/age-recipients.txt, identity matching those recipients.
# Usage:
#   make rehearsal-offhost BACKUP_DEST=/var/tmp/casino_bot_offhost/ \
#        AGE_IDENTITY_FILE=$$HOME/.config/casino_bot/age-identity.txt
rehearsal-offhost:
	@if [ -z "$(BACKUP_DEST)" ]; then echo "FAIL: BACKUP_DEST not set (local directory)"; exit 2; fi
	BACKUP_DEST=$(BACKUP_DEST) \
	  AGE_IDENTITY_FILE="$${AGE_IDENTITY_FILE}" \
	  ENV_FILE="$${ENV_FILE:-.env.prod.example}" \
	  COMPOSE_FILE="$${COMPOSE_FILE:-docker-compose.prod.yml}" \
	  RESTORE_ENV_FILE="$${RESTORE_ENV_FILE:-.env.restore.example}" \
	  HOST_HEADER="$${HOST_HEADER:-api.example.com}" \
	  KEEP_STACK="$${KEEP_STACK:-false}" \
	  ./scripts/ops/rehearsal_offhost_full.sh

# Shell lint gate (M5W3): bash -n always; shellcheck if installed.
# REQUIRE_SHELLCHECK=1 fails closed when shellcheck is missing (used in CI).
shell-lint:
	./scripts/lint_shell.sh

shell-lint-strict:
	REQUIRE_SHELLCHECK=1 ./scripts/lint_shell.sh

# Backup retention (M5W3) — see docs/ops/backup-retention-policy.md
backup-retention-dry-run:
	./scripts/ops/backup_retention.sh

backup-retention-apply:
	APPLY=true ./scripts/ops/backup_retention.sh

# Backup manifest verification (M5W4) — schema + sha256 + provenance.
# Usage:
#   make verify-backup-manifest MANIFEST=./backups/<file>.dump.age
#   make verify-backup-manifest MANIFEST=./backups/<file>.dump.age.meta.json \
#        REQUIRED_FIELDS=git_sha,alembic_revision
verify-backup-manifest:
	@if [ -z "$(MANIFEST)" ]; then echo "FAIL: MANIFEST not set"; exit 2; fi
	@flags=""; \
	  if [ -n "$(REQUIRED_FIELDS)" ]; then flags="--require-fields $(REQUIRED_FIELDS)"; fi; \
	  python3 scripts/ops/verify_backup_manifest.py $$flags $(MANIFEST)

# Scheduled restore-verification drill (M5W4) — produces a JSON report
# under artifacts/reports/restore-drills/. Suitable for cron.
scheduled-restore-drill:
	./scripts/ops/scheduled_restore_drill.sh

# Operational evidence retention (M5W4) — keep last N PASS reports;
# move FAIL reports to archive/ on first apply pass.
evidence-retention-dry-run:
	./scripts/ops/evidence_retention.sh

evidence-retention-apply:
	APPLY=true ./scripts/ops/evidence_retention.sh

# Ops contract smoke (M6W1) — no-Docker regression gate that asserts
# verify_backup_manifest / scheduled_restore_drill / evidence_retention /
# backup_retention all behave per contract on synthetic fixtures.
ops-contract-smoke:
	./scripts/ops/ops_contract_smoke.sh

# Long-run restore-drill loop validation (M6W1) — N iterations + retention
# on a per-invocation tempdir; prints PASS/FAIL summary.
restore-drill-loop-validate:
	./scripts/ops/restore_drill_loop_validate.sh

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
