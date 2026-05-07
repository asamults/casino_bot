#!/usr/bin/env bash
# restore_isolated_compose.sh -- restore an encrypted backup into an isolated
# Docker Compose stack that does NOT touch the running prod compose project.
#
# Pipeline:
#   1) decrypt BACKUP_FILE (.dump.age | .dump.gpg) into a temp .dump
#   2) verify sha256 sidecar (if present) before decrypt
#   3) bring up an isolated stack:
#        COMPOSE_PROJECT_NAME = casino_bot_restore_<UTC timestamp>
#        compose file         = docker-compose.restore.yml (no fixed container_name)
#   4) pg_restore the .dump into the isolated postgres
#   5) start the isolated api, then run pg_verify_compose.sh against it
#   6) print PASS/FAIL and the project name (for cleanup)
#
# Inputs:
#   BACKUP_FILE              (required) path to encrypted backup
#   AGE_IDENTITY_FILE        path to age private identity (required if .age)
#   GPG_PASSPHRASE_FILE      path to gpg passphrase (optional, for .gpg)
#   ENV_FILE                 default: .env.restore.example
#   RESTORE_COMPOSE_FILE     default: docker-compose.restore.yml
#   COMPOSE_PROJECT_PREFIX   default: casino_bot_restore
#   HOST_HEADER              default: api.example.com
#   KEEP_STACK               true|false (default: false). If true, leave the
#                            isolated stack running for inspection. If false,
#                            tear it down on success.
#   VERIFY_CHECKSUM          true|false (default: true)
#
# Exit codes:
#   0 ok
#   2 bad input
#   3 decryption / restore / verify failure

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_FILE="${BACKUP_FILE:?BACKUP_FILE is required (path to .dump.age|.dump.gpg)}"
ENV_FILE="${ENV_FILE:-.env.restore.example}"
RESTORE_COMPOSE_FILE="${RESTORE_COMPOSE_FILE:-docker-compose.restore.yml}"
COMPOSE_PROJECT_PREFIX="${COMPOSE_PROJECT_PREFIX:-casino_bot_restore}"
HOST_HEADER="${HOST_HEADER:-api.example.com}"
KEEP_STACK="${KEEP_STACK:-false}"
VERIFY_CHECKSUM="${VERIFY_CHECKSUM:-true}"
AGE_IDENTITY_FILE="${AGE_IDENTITY_FILE:-${HOME}/.config/casino_bot/age-identity.txt}"
GPG_PASSPHRASE_FILE="${GPG_PASSPHRASE_FILE:-}"

if [[ ! -s "$BACKUP_FILE" ]]; then
  echo "FAIL: BACKUP_FILE not found or empty: $BACKUP_FILE" >&2
  exit 2
fi
if [[ ! -s "$ENV_FILE" ]]; then
  echo "FAIL: ENV_FILE not found or empty: $ENV_FILE" >&2
  exit 2
fi
if [[ ! -s "$RESTORE_COMPOSE_FILE" ]]; then
  echo "FAIL: RESTORE_COMPOSE_FILE not found: $RESTORE_COMPOSE_FILE" >&2
  exit 2
fi

TS="$(date -u +%Y%m%dT%H%M%SZ)"
PROJECT="${COMPOSE_PROJECT_PREFIX}_${TS}"
SHA_FILE="${BACKUP_FILE}.sha256"

echo "== restore_isolated_compose =="
echo "Project:  $PROJECT"
echo "Compose:  $RESTORE_COMPOSE_FILE"
echo "Env:      $ENV_FILE"
echo "Backup:   $BACKUP_FILE"
echo "Keep:     $KEEP_STACK"

# --- 0) checksum verify ---------------------------------------------------
if [[ "$VERIFY_CHECKSUM" == "true" && -s "$SHA_FILE" ]]; then
  echo "-- verifying sha256 sidecar --"
  ( cd "$(dirname "$BACKUP_FILE")" && sha256sum -c "$(basename "$SHA_FILE")" )
fi

# --- 1) decrypt ----------------------------------------------------------
TMP_DIR="$(mktemp -d)"
cleanup_tmp() {
  if [[ -n "${TMP_DIR:-}" && -d "$TMP_DIR" ]]; then
    if command -v shred >/dev/null 2>&1; then
      find "$TMP_DIR" -type f -exec shred -u {} + 2>/dev/null || true
    fi
    rm -rf "$TMP_DIR"
  fi
}
trap cleanup_tmp EXIT

DUMP_PATH="$TMP_DIR/restore.dump"

case "$BACKUP_FILE" in
  *.age)
    if ! command -v age >/dev/null 2>&1; then
      echo "FAIL: 'age' is not installed but BACKUP_FILE is .age" >&2
      exit 2
    fi
    if [[ ! -s "$AGE_IDENTITY_FILE" ]]; then
      echo "FAIL: AGE_IDENTITY_FILE not found: $AGE_IDENTITY_FILE" >&2
      echo "      generate with: age-keygen -o \"$AGE_IDENTITY_FILE\"" >&2
      exit 2
    fi
    echo "-- decrypting with age --"
    age -d -i "$AGE_IDENTITY_FILE" -o "$DUMP_PATH" "$BACKUP_FILE"
    ;;
  *.gpg)
    if ! command -v gpg >/dev/null 2>&1; then
      echo "FAIL: 'gpg' is not installed but BACKUP_FILE is .gpg" >&2
      exit 2
    fi
    echo "-- decrypting with gpg --"
    if [[ -n "$GPG_PASSPHRASE_FILE" && -s "$GPG_PASSPHRASE_FILE" ]]; then
      gpg --batch --yes --pinentry-mode loopback \
          --passphrase-file "$GPG_PASSPHRASE_FILE" \
          --output "$DUMP_PATH" --decrypt "$BACKUP_FILE"
    else
      gpg --batch --yes --output "$DUMP_PATH" --decrypt "$BACKUP_FILE"
    fi
    ;;
  *)
    echo "FAIL: unrecognized backup extension (expected .age or .gpg): $BACKUP_FILE" >&2
    exit 2
    ;;
esac

if [[ ! -s "$DUMP_PATH" ]]; then
  echo "FAIL: decrypted dump is empty: $DUMP_PATH" >&2
  exit 3
fi

# --- 2) start isolated stack ---------------------------------------------
COMPOSE_BASE=(docker compose --env-file "$ENV_FILE" -f "$RESTORE_COMPOSE_FILE" -p "$PROJECT")

teardown() {
  if [[ "$KEEP_STACK" != "true" ]]; then
    echo "-- tearing down isolated stack ($PROJECT) --"
    "${COMPOSE_BASE[@]}" down -v --remove-orphans || true
  else
    echo "-- KEEP_STACK=true; leaving stack up: $PROJECT --"
    echo "   to clean up later: docker compose -p $PROJECT -f $RESTORE_COMPOSE_FILE down -v"
  fi
}
trap 'teardown; cleanup_tmp' EXIT

echo "-- starting isolated postgres --"
"${COMPOSE_BASE[@]}" up -d postgres

PG_CONTAINER="$("${COMPOSE_BASE[@]}" ps -q postgres)"
if [[ -z "$PG_CONTAINER" ]]; then
  echo "FAIL: could not resolve isolated postgres container id" >&2
  exit 3
fi

echo "-- waiting for isolated postgres to be healthy --"
for _ in $(seq 1 60); do
  status="$(docker inspect --format='{{.State.Health.Status}}' "$PG_CONTAINER" 2>/dev/null || true)"
  if [[ "$status" == "healthy" ]]; then break; fi
  sleep 1
done
if [[ "$status" != "healthy" ]]; then
  echo "FAIL: isolated postgres did not become healthy" >&2
  exit 3
fi

# --- 3) pg_restore -------------------------------------------------------
echo "-- pg_restore into isolated DB --"
PG_USER="$(grep -E '^POSTGRES_USER=' "$ENV_FILE" | cut -d= -f2-)"
PG_DB="$(grep -E '^POSTGRES_DB=' "$ENV_FILE" | cut -d= -f2-)"
cat "$DUMP_PATH" | "${COMPOSE_BASE[@]}" exec -T postgres \
  pg_restore --clean --if-exists -U "$PG_USER" -d "$PG_DB"

# --- 4) start api + verify -----------------------------------------------
echo "-- starting isolated api --"
"${COMPOSE_BASE[@]}" up -d --build api

API_CONTAINER="$("${COMPOSE_BASE[@]}" ps -q api)"
if [[ -z "$API_CONTAINER" ]]; then
  echo "FAIL: could not resolve isolated api container id" >&2
  exit 3
fi

echo "-- verifying probes against isolated api ($API_CONTAINER) --"
HOST_HEADER="$HOST_HEADER" \
ENV_FILE="$ENV_FILE" \
COMPOSE_FILE="$RESTORE_COMPOSE_FILE" \
API_CONTAINER="$API_CONTAINER" \
  "$ROOT_DIR/scripts/ops/pg_verify_compose.sh"

echo "PASS: isolated restore verified"
echo "Project: $PROJECT"
