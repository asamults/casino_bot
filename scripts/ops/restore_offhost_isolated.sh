#!/usr/bin/env bash
# restore_offhost_isolated.sh -- M6W3 contract wrapper:
#   off-host encrypted backup -> (optional fetch) -> decrypt -> isolated restore -> probes
#
# Supports BACKUP_SRC as:
#   - local file path:                  /var/backups/.../casino_bot_*.dump.age
#   - remote SSH scp source:            user@host:/var/backups/.../casino_bot_*.dump.age
#
# Required env:
#   BACKUP_SRC              local path or scp source to encrypted backup
#
# Decryption inputs (forwarded to restore_isolated_compose.sh):
#   AGE_IDENTITY_FILE       required for .age (default: ~/.config/casino_bot/age-identity.txt)
#   GPG_PASSPHRASE_FILE     optional for .gpg
#
# Restore inputs:
#   ENV_FILE                restore env (default: .env.restore.example)
#   RESTORE_COMPOSE_FILE    default: docker-compose.restore.yml
#   HOST_HEADER             default: api.example.com
#   KEEP_STACK              true|false (default: false)
#
# Optional behavior:
#   VERIFY_MANIFEST         true|false (default: true) - if <backup>.meta.json exists locally,
#                           validate it + sha256 before restore.
#   FETCH_TOOL              auto|scp (default: auto) - remote fetch method
#
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_SRC="${BACKUP_SRC:?BACKUP_SRC is required (local path or user@host:/path/file.dump.age)}"
VERIFY_MANIFEST="${VERIFY_MANIFEST:-true}"
FETCH_TOOL="${FETCH_TOOL:-auto}"

ENV_FILE="${ENV_FILE:-.env.restore.example}"
RESTORE_COMPOSE_FILE="${RESTORE_COMPOSE_FILE:-docker-compose.restore.yml}"
HOST_HEADER="${HOST_HEADER:-api.example.com}"
KEEP_STACK="${KEEP_STACK:-false}"

AGE_IDENTITY_FILE="${AGE_IDENTITY_FILE:-${HOME}/.config/casino_bot/age-identity.txt}"
GPG_PASSPHRASE_FILE="${GPG_PASSPHRASE_FILE:-}"
SSH_OPTS="${SSH_OPTS:-}"

echo "== restore_offhost_isolated (M6W3) =="
echo "Src:      $BACKUP_SRC"
echo "Env:      $ENV_FILE"
echo "Compose:  $RESTORE_COMPOSE_FILE"
echo "Keep:     $KEEP_STACK"

is_remote=false
if [[ "$BACKUP_SRC" == *":"* && "$BACKUP_SRC" != /* ]]; then
  is_remote=true
fi

LOCAL_BACKUP="$BACKUP_SRC"
TMP_DIR=""
cleanup_fetch_tmp() {
  local code=$?
  if [[ -n "${TMP_DIR:-}" && -d "$TMP_DIR" ]]; then
    rm -rf "$TMP_DIR"
  fi
  exit $code
}

if $is_remote; then
  if [[ "$FETCH_TOOL" == "auto" ]]; then
    FETCH_TOOL="scp"
  fi
  if [[ "$FETCH_TOOL" != "scp" ]]; then
    echo "FAIL: unsupported FETCH_TOOL=$FETCH_TOOL (use scp)" >&2
    exit 2
  fi
  if ! command -v scp >/dev/null 2>&1; then
    echo "FAIL: scp is required to fetch remote BACKUP_SRC" >&2
    exit 2
  fi
  TMP_DIR="$(mktemp -d)"
  trap cleanup_fetch_tmp EXIT
  echo "-- fetching remote backup via scp --"
  # shellcheck disable=SC2086
  scp $SSH_OPTS "$BACKUP_SRC" "$TMP_DIR/"
  LOCAL_BACKUP="$TMP_DIR/$(basename "$BACKUP_SRC")"
fi

if [[ ! -s "$LOCAL_BACKUP" ]]; then
  echo "FAIL: backup file missing or empty after fetch: $LOCAL_BACKUP" >&2
  exit 2
fi

if [[ "$VERIFY_MANIFEST" == "true" ]]; then
  meta="${LOCAL_BACKUP}.meta.json"
  if [[ -s "$meta" ]]; then
    echo "-- verifying backup manifest + sha256 --"
    "$ROOT_DIR/scripts/ops/verify_backup_manifest.py" "$meta"
  else
    echo "(skipped) manifest verify: ${meta} not present"
  fi
fi

echo "-- restoring into isolated compose project --"
BACKUP_FILE="$LOCAL_BACKUP" \
AGE_IDENTITY_FILE="$AGE_IDENTITY_FILE" \
GPG_PASSPHRASE_FILE="$GPG_PASSPHRASE_FILE" \
ENV_FILE="$ENV_FILE" \
RESTORE_COMPOSE_FILE="$RESTORE_COMPOSE_FILE" \
HOST_HEADER="$HOST_HEADER" \
KEEP_STACK="$KEEP_STACK" \
COMPOSE_PROJECT_PREFIX="restore" \
  "$ROOT_DIR/scripts/ops/restore_isolated_compose.sh"

