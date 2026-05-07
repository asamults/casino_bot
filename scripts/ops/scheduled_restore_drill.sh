#!/usr/bin/env bash
# scheduled_restore_drill.sh — automated, schedulable restore-verification
# drill (M5W4).
#
# What it does:
#   1) Finds the newest *.dump.age / *.dump.gpg under BACKUP_DIR.
#   2) Verifies its manifest with verify_backup_manifest.py (schema + sha256).
#   3) Runs scripts/ops/restore_isolated_compose.sh against an isolated
#      Compose project (project name: casino_bot_restore_<UTC>).
#   4) Writes a structured JSON report to:
#         artifacts/reports/restore-drills/<UTC>.json
#      with status PASS or FAIL, durations, the backup file used, and the
#      isolated project name.
#   5) Exits 0 on PASS, non-zero on FAIL.
#
# The report path is the operational evidence artifact this milestone is
# meant to produce. Pair this with scripts/ops/evidence_retention.sh.
#
# Inputs (env):
#   BACKUP_DIR              default: ./backups
#   AGE_IDENTITY_FILE       default: $HOME/.config/casino_bot/age-identity.txt
#   GPG_PASSPHRASE_FILE     default: ""
#   ENV_FILE                default: .env.restore.example
#   RESTORE_COMPOSE_FILE    default: docker-compose.restore.yml
#   HOST_HEADER             default: api.example.com
#   REPORT_DIR              default: artifacts/reports/restore-drills
#   KEEP_STACK              true|false (default: false)
#   REQUIRED_MANIFEST_FIELDS comma-separated; passed to verify_backup_manifest
#
# Exit codes:
#   0 PASS
#   2 bad input (no backups, missing tool)
#   3 FAIL during verification or restore
#
# Cron usage:
#   30 4 * * *  cd /opt/casino_bot && ./scripts/ops/scheduled_restore_drill.sh \
#                 >> /var/log/casino_bot/restore_drill.log 2>&1

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
AGE_IDENTITY_FILE="${AGE_IDENTITY_FILE:-${HOME}/.config/casino_bot/age-identity.txt}"
GPG_PASSPHRASE_FILE="${GPG_PASSPHRASE_FILE:-}"
ENV_FILE="${ENV_FILE:-.env.restore.example}"
RESTORE_COMPOSE_FILE="${RESTORE_COMPOSE_FILE:-docker-compose.restore.yml}"
HOST_HEADER="${HOST_HEADER:-api.example.com}"
REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/artifacts/reports/restore-drills}"
KEEP_STACK="${KEEP_STACK:-false}"
REQUIRED_MANIFEST_FIELDS="${REQUIRED_MANIFEST_FIELDS:-}"

mkdir -p "$REPORT_DIR"

START_EPOCH="$(date +%s)"
START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TS_FILE="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT_PATH="$REPORT_DIR/$TS_FILE.json"

# State updated as the drill progresses; consumed by emit_report on EXIT.
status="FAIL"
reason="(no progress)"
manifest_verified=false
isolated_project=""
backup_file=""
verify_seconds=0
restore_seconds=0

# --- helpers ---------------------------------------------------------------
_json_str() {
  python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$1"
}

emit_report() {
  local end_epoch end_utc duration
  end_epoch="$(date +%s)"
  end_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  duration=$(( end_epoch - START_EPOCH ))
  cat > "$REPORT_PATH" <<JSON
{
  "schema_version": 1,
  "result": "$status",
  "reason": $(_json_str "$reason"),
  "backup_dir": $(_json_str "$BACKUP_DIR"),
  "backup_file": $(_json_str "$backup_file"),
  "manifest_verified": $manifest_verified,
  "isolated_project": $(_json_str "$isolated_project"),
  "started_at_utc": "$START_UTC",
  "ended_at_utc": "$end_utc",
  "duration_seconds": $duration,
  "verify_seconds": $verify_seconds,
  "restore_seconds": $restore_seconds,
  "host_header": $(_json_str "$HOST_HEADER"),
  "compose_file": $(_json_str "$RESTORE_COMPOSE_FILE"),
  "env_file": $(_json_str "$ENV_FILE")
}
JSON
  echo "Report: $REPORT_PATH"
  echo "Result: $status"
}

# tmp file holding the restore script's combined stdout/stderr (best-effort).
RESTORE_LOG="$(mktemp)"
cleanup_tmp() {
  rm -f "$RESTORE_LOG"
}
trap 'cleanup_tmp; emit_report' EXIT

# --- 1) pick the newest backup --------------------------------------------
echo "== scheduled_restore_drill =="
echo "Backup dir:    $BACKUP_DIR"
echo "Report path:   $REPORT_PATH"

shopt -s nullglob
candidates=("$BACKUP_DIR"/*.dump.age "$BACKUP_DIR"/*.dump.gpg)
shopt -u nullglob
if [[ "${#candidates[@]}" -eq 0 ]]; then
  reason="no encrypted backups found in BACKUP_DIR"
  echo "FAIL: $reason" >&2
  exit 2
fi
backup_file=""
latest_mtime=0
for f in "${candidates[@]}"; do
  m=$(stat -c '%Y' "$f" 2>/dev/null || stat -f '%m' "$f")
  if [[ "$m" -gt "$latest_mtime" ]]; then
    latest_mtime=$m
    backup_file=$f
  fi
done
echo "Picked latest: $backup_file"

# --- 2) verify manifest ---------------------------------------------------
echo "-- verifying manifest --"
verify_args=("$backup_file")
if [[ -n "$REQUIRED_MANIFEST_FIELDS" ]]; then
  verify_args+=(--require-fields "$REQUIRED_MANIFEST_FIELDS")
fi
v_start="$(date +%s)"
if ! python3 "$ROOT_DIR/scripts/ops/verify_backup_manifest.py" "${verify_args[@]}"; then
  reason="manifest verification failed"
  exit 3
fi
verify_seconds=$(( $(date +%s) - v_start ))
manifest_verified=true

# --- 3) restore in isolated stack -----------------------------------------
echo "-- running isolated restore --"
r_start="$(date +%s)"
if BACKUP_FILE="$backup_file" \
   AGE_IDENTITY_FILE="$AGE_IDENTITY_FILE" \
   GPG_PASSPHRASE_FILE="$GPG_PASSPHRASE_FILE" \
   ENV_FILE="$ENV_FILE" \
   RESTORE_COMPOSE_FILE="$RESTORE_COMPOSE_FILE" \
   HOST_HEADER="$HOST_HEADER" \
   KEEP_STACK="$KEEP_STACK" \
   "$ROOT_DIR/scripts/ops/restore_isolated_compose.sh" 2>&1 | tee "$RESTORE_LOG"; then
  status="PASS"
  reason="ok"
else
  reason="restore_isolated_compose.sh exited non-zero (see drill log)"
fi
restore_seconds=$(( $(date +%s) - r_start ))

# Best-effort: extract the isolated project name from the restore script's stdout.
isolated_project="$(grep -oE 'casino_bot_restore_[0-9TZ]+' "$RESTORE_LOG" | tail -n1 || true)"

if [[ "$status" != "PASS" ]]; then
  exit 3
fi
exit 0
