#!/usr/bin/env bash
# rehearsal_offhost_full.sh — one-shot M5W2 dry-run:
#   pg_dump → encrypt → off-host copy (local DEST) → isolated restore → probes
#
# Env:
#   BACKUP_DEST        (required) local directory, e.g. /var/tmp/casino_bot_offhost/
#   AGE_IDENTITY_FILE    default: $HOME/.config/casino_bot/age-identity.txt
#   ENV_FILE             forwarded to pg_backup_encrypt (source compose dump)
#   COMPOSE_FILE         forwarded to pg_backup_encrypt
#   RESTORE_ENV_FILE     passed as ENV_FILE to restore_isolated_compose
#   HOST_HEADER          forwarded to restore_isolated_compose
#   KEEP_STACK           forwarded to restore_isolated_compose
#   BACKUP_ENCRYPT_TOOL, AGE_RECIPIENTS_FILE, GPG_*, SSH_OPTS, etc. as in sub-scripts
#
# Remote BACKUP_DEST (user@host:path) is not supported here: copy succeeds but restore
# needs a local path; use the split Makefile targets or pull the artifact first.

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DEST="${BACKUP_DEST:?BACKUP_DEST is required (local directory, trailing / recommended)}"
AGE_IDENTITY_FILE="${AGE_IDENTITY_FILE:-${HOME}/.config/casino_bot/age-identity.txt}"
ENV_FILE="${ENV_FILE:-.env.prod.example}"
RESTORE_ENV_FILE="${RESTORE_ENV_FILE:-.env.restore.example}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

if [[ "$BACKUP_DEST" == *:* ]] && [[ "$BACKUP_DEST" != /* ]]; then
  echo "FAIL: rehearsal_offhost_full.sh only supports a LOCAL BACKUP_DEST." >&2
  echo "      For SSH destinations use: make backup-offhost BACKUP_DEST=user@host:... then restore from a local copy." >&2
  exit 2
fi

echo "== rehearsal_offhost_full (M5W2) =="
echo "Dump env:    $ENV_FILE compose=$COMPOSE_FILE"
echo "Restore env: $RESTORE_ENV_FILE"
echo "Off-host:    $BACKUP_DEST"

mkdir -p "$BACKUP_DEST"

ENV_FILE="$ENV_FILE" COMPOSE_FILE="$COMPOSE_FILE" \
  "$ROOT_DIR/scripts/ops/pg_backup_encrypt.sh"

shopt -s nullglob
candidates=(backups/*.dump.age backups/*.dump.gpg)
shopt -u nullglob
if [[ ${#candidates[@]} -eq 0 ]]; then
  echo "FAIL: no encrypted artifact under backups/" >&2
  exit 2
fi
# newest by mtime
latest=""
latest_mtime=0
for f in "${candidates[@]}"; do
  m=$(stat -c '%Y' "$f" 2>/dev/null || stat -f '%m' "$f")
  if [[ "$m" -gt "$latest_mtime" ]]; then
    latest_mtime=$m
    latest=$f
  fi
done

echo "-- off-host copy -> $BACKUP_DEST --"
BACKUP_FILE="$latest" BACKUP_DEST="$BACKUP_DEST" \
  "$ROOT_DIR/scripts/ops/backup_offhost_copy.sh"

copied="$BACKUP_DEST/$(basename "$latest")"
if [[ ! -s "$copied" ]]; then
  echo "FAIL: expected encrypted file at $copied" >&2
  exit 3
fi

echo "-- isolated restore from copy --"
BACKUP_FILE="$copied" \
  AGE_IDENTITY_FILE="$AGE_IDENTITY_FILE" \
  ENV_FILE="$RESTORE_ENV_FILE" \
  HOST_HEADER="${HOST_HEADER:-api.example.com}" \
  KEEP_STACK="${KEEP_STACK:-false}" \
  "$ROOT_DIR/scripts/ops/restore_isolated_compose.sh"

echo "PASS: M5W2 full rehearsal (backup → encrypt → copy → isolated restore → probes)"
