#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.prod.example}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"
API_SERVICE="${API_SERVICE:-api}"
BACKUP_PATH="${BACKUP_PATH:?required (path to .dump from pg_dump -Fc)}"
DESTROY_VOLUME="${DESTROY_VOLUME:-true}"

echo "== pg_restore (compose) =="
echo "Compose: $COMPOSE_FILE env=$ENV_FILE"
echo "Backup: $BACKUP_PATH"
echo "Destroy volume: $DESTROY_VOLUME"

if [[ ! -f "$BACKUP_PATH" ]]; then
  echo "FAIL: backup file not found: $BACKUP_PATH" >&2
  exit 2
fi

echo "-- stopping stack --"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down

if [[ "$DESTROY_VOLUME" == "true" ]]; then
  echo "-- destroying pgdata volume --"
  docker volume rm -f casino_bot_pgdata 2>/dev/null || true
fi

echo "-- starting fresh Postgres --"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d "$POSTGRES_SERVICE"

echo "Waiting for Postgres to be healthy..."
for i in {1..60}; do
  status="$(docker inspect --format='{{.State.Health.Status}}' casino_bot-postgres 2>/dev/null || true)"
  if [[ "$status" == "healthy" ]]; then
    break
  fi
  sleep 1
done

echo "-- restoring dump --"
cat "$BACKUP_PATH" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T "$POSTGRES_SERVICE" \
  pg_restore --clean --if-exists \
  -U "$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)" \
  -d "$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)"

echo "-- starting api and running migrations/smoke --"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build "$API_SERVICE"

echo "OK: restore complete (api started)"

