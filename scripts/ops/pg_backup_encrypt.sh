#!/usr/bin/env bash
# pg_backup_encrypt.sh -- compose pg_dump + at-rest encryption + checksum + meta.
#
# Pipeline:
#   1) call scripts/ops/pg_dump_compose.sh  -> backups/<name>.dump
#   2) encrypt to backups/<name>.dump.<ext> using age (default) or gpg
#   3) write <name>.dump.<ext>.sha256
#   4) write <name>.dump.<ext>.meta.json   (timestamp, sizes, recipient, tool)
#   5) (optional) shred the plaintext .dump
#
# Required tools: docker, sha256sum, jq is NOT required (we emit JSON ourselves).
# Encryption tool: `age` (default) or `gpg`. Selectable via BACKUP_ENCRYPT_TOOL.
#
# Env:
#   BACKUP_ENCRYPT_TOOL   age | gpg                       (default: age)
#   AGE_RECIPIENTS_FILE   path to age recipients          (default: ops/backup/age-recipients.txt)
#   GPG_RECIPIENT         gpg recipient key id / email    (required if tool=gpg)
#   KEEP_PLAINTEXT        true|false                      (default: false)
#   ENV_FILE / COMPOSE_FILE / BACKUP_DIR / BACKUP_NAME / POSTGRES_SERVICE
#       -> forwarded to pg_dump_compose.sh
#
# Outputs (ENC_FILE format):
#   age -> <name>.dump.age
#   gpg -> <name>.dump.gpg
#
# Exit codes:
#   0  ok
#   2  bad input / missing tool / missing recipient
#   3  encryption or checksum failure

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_ENCRYPT_TOOL="${BACKUP_ENCRYPT_TOOL:-age}"
AGE_RECIPIENTS_FILE="${AGE_RECIPIENTS_FILE:-ops/backup/age-recipients.txt}"
GPG_RECIPIENT="${GPG_RECIPIENT:-}"
KEEP_PLAINTEXT="${KEEP_PLAINTEXT:-false}"

BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
BACKUP_NAME="${BACKUP_NAME:-casino_bot_$(date -u +%Y%m%dT%H%M%SZ).dump}"
ENV_FILE="${ENV_FILE:-.env.prod.example}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
POSTGRES_SERVICE="${POSTGRES_SERVICE:-postgres}"

mkdir -p "$BACKUP_DIR"
DUMP_PATH="$BACKUP_DIR/$BACKUP_NAME"

echo "== pg_backup_encrypt =="
echo "Tool:    $BACKUP_ENCRYPT_TOOL"
echo "Dump:    $DUMP_PATH"

# --- 1) plaintext dump ----------------------------------------------------
BACKUP_DIR="$BACKUP_DIR" \
BACKUP_NAME="$BACKUP_NAME" \
ENV_FILE="$ENV_FILE" \
COMPOSE_FILE="$COMPOSE_FILE" \
POSTGRES_SERVICE="$POSTGRES_SERVICE" \
  "$ROOT_DIR/scripts/ops/pg_dump_compose.sh"

if [[ ! -s "$DUMP_PATH" ]]; then
  echo "FAIL: dump file missing or empty: $DUMP_PATH" >&2
  exit 3
fi

# --- 2) encrypt ----------------------------------------------------------
case "$BACKUP_ENCRYPT_TOOL" in
  age)
    if ! command -v age >/dev/null 2>&1; then
      echo "FAIL: 'age' is not installed (https://age-encryption.org/)." >&2
      exit 2
    fi
    if [[ ! -s "$AGE_RECIPIENTS_FILE" ]]; then
      echo "FAIL: AGE_RECIPIENTS_FILE not found or empty: $AGE_RECIPIENTS_FILE" >&2
      echo "      copy ops/backup/age-recipients.txt.example and add real keys." >&2
      exit 2
    fi
    ENC_PATH="${DUMP_PATH}.age"
    echo "-- encrypting with age --"
    age -R "$AGE_RECIPIENTS_FILE" -o "$ENC_PATH" "$DUMP_PATH"
    RECIPIENT_DESC="age:$AGE_RECIPIENTS_FILE"
    ;;
  gpg)
    if ! command -v gpg >/dev/null 2>&1; then
      echo "FAIL: 'gpg' is not installed." >&2
      exit 2
    fi
    if [[ -z "$GPG_RECIPIENT" ]]; then
      echo "FAIL: BACKUP_ENCRYPT_TOOL=gpg requires GPG_RECIPIENT=<keyid|email>." >&2
      exit 2
    fi
    ENC_PATH="${DUMP_PATH}.gpg"
    echo "-- encrypting with gpg (recipient: $GPG_RECIPIENT) --"
    gpg --batch --yes --trust-model always \
        --output "$ENC_PATH" \
        --encrypt --recipient "$GPG_RECIPIENT" "$DUMP_PATH"
    RECIPIENT_DESC="gpg:$GPG_RECIPIENT"
    ;;
  *)
    echo "FAIL: unsupported BACKUP_ENCRYPT_TOOL=$BACKUP_ENCRYPT_TOOL (use age|gpg)" >&2
    exit 2
    ;;
esac

if [[ ! -s "$ENC_PATH" ]]; then
  echo "FAIL: encrypted file missing or empty: $ENC_PATH" >&2
  exit 3
fi

# --- 3) checksum ----------------------------------------------------------
SHA_PATH="${ENC_PATH}.sha256"
( cd "$BACKUP_DIR" && sha256sum "$(basename "$ENC_PATH")" > "$SHA_PATH" )
echo "Checksum: $SHA_PATH"

# --- 4) metadata ----------------------------------------------------------
META_PATH="${ENC_PATH}.meta.json"
PLAIN_SIZE="$(stat -c '%s' "$DUMP_PATH" 2>/dev/null || stat -f '%z' "$DUMP_PATH")"
ENC_SIZE="$(stat -c '%s' "$ENC_PATH" 2>/dev/null || stat -f '%z' "$ENC_PATH")"
SHA_VALUE="$(awk '{print $1}' "$SHA_PATH")"
TS_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

cat > "$META_PATH" <<JSON
{
  "schema_version": 1,
  "created_at_utc": "$TS_UTC",
  "tool": "$BACKUP_ENCRYPT_TOOL",
  "recipient": "$RECIPIENT_DESC",
  "plaintext_basename": "$(basename "$DUMP_PATH")",
  "encrypted_basename": "$(basename "$ENC_PATH")",
  "plaintext_size_bytes": $PLAIN_SIZE,
  "encrypted_size_bytes": $ENC_SIZE,
  "sha256": "$SHA_VALUE",
  "compose_file": "$COMPOSE_FILE",
  "env_file": "$ENV_FILE",
  "postgres_service": "$POSTGRES_SERVICE"
}
JSON
echo "Metadata: $META_PATH"

# --- 5) cleanup plaintext ------------------------------------------------
if [[ "$KEEP_PLAINTEXT" != "true" ]]; then
  echo "-- removing plaintext dump (KEEP_PLAINTEXT=$KEEP_PLAINTEXT) --"
  if command -v shred >/dev/null 2>&1; then
    shred -u "$DUMP_PATH"
  else
    rm -f "$DUMP_PATH"
  fi
fi

ls -lh "$ENC_PATH" "$SHA_PATH" "$META_PATH"
echo "OK: encrypted backup ready -> $ENC_PATH"
