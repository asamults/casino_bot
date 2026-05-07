#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.prod.example}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
BACKUP_NAME="${BACKUP_NAME:-casino_bot_$(date -u +%Y%m%dT%H%M%SZ).dump}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"

mkdir -p "$BACKUP_DIR"
OUT_PATH="$BACKUP_DIR/$BACKUP_NAME"

echo "== pg_dump (compose) =="
echo "Compose: $COMPOSE_FILE env=$ENV_FILE service=$POSTGRES_SERVICE"
echo "Output: $OUT_PATH"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d "$POSTGRES_SERVICE"

echo "Waiting for Postgres to be healthy..."
for _ in {1..60}; do
  status="$(docker inspect --format='{{.State.Health.Status}}' casino_bot-postgres 2>/dev/null || true)"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 1
done

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_dump -Fc -U "$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)" \
  -d "$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)" > "$OUT_PATH"

ls -lh "$OUT_PATH"
echo "OK: backup created"

