#!/usr/bin/env bash
# restore_drill_loop_validate.sh — long-run confidence harness for the
# restore-drill / evidence-retention pipeline (M6W1).
#
# What this proves (without spinning up Docker):
#
#   * scheduled_restore_drill.sh can be invoked back-to-back N times
#     and produces a uniquely-named JSON report each iteration.
#   * The reports are well-formed (parseable JSON with the M6W1 fields).
#   * evidence_retention.sh, run mid-loop, correctly trims old PASS
#     reports, archives FAIL reports, and is idempotent across reruns.
#   * Mixing synthesized PASS reports (representing prior weeks) with
#     freshly-generated FAIL reports (from the no-backup test path)
#     gives a realistic "many weeks of drills" picture for retention.
#
# This is a *contract* loop: it does NOT verify that a real Docker
# restore works end-to-end. That is a separate exercise that needs a
# full compose stack and a real encrypted artifact.
#
# Inputs (env):
#   ITERATIONS   number of drill invocations (default: 5)
#   KEEP_LAST    KEEP_LAST passed to evidence_retention (default: 3)
#   PRIOR_PASS   number of synthetic prior-week PASS reports to seed
#                before the loop (default: 5)
#   OUT_DIR      working directory (default: a fresh tempdir)
#
# Exit codes:
#   0 PASS
#   2 any contract violation

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ITERATIONS="${ITERATIONS:-5}"
KEEP_LAST="${KEEP_LAST:-3}"
PRIOR_PASS="${PRIOR_PASS:-5}"
OUT_DIR="${OUT_DIR:-$(mktemp -d -t casino_bot_drill_loop.XXXXXX)}"

if ! [[ "$ITERATIONS" =~ ^[1-9][0-9]*$ ]]; then
  echo "FAIL: ITERATIONS must be a positive integer (got: $ITERATIONS)" >&2
  exit 2
fi

REPORT_DIR="$OUT_DIR/reports"
BACKUP_DIR="$OUT_DIR/backups"
mkdir -p "$REPORT_DIR" "$BACKUP_DIR"

echo "== restore_drill_loop_validate =="
echo "Iterations:    $ITERATIONS"
echo "Prior PASS:    $PRIOR_PASS (synthetic)"
echo "Keep last:     $KEEP_LAST"
echo "Working dir:   $OUT_DIR"
echo

# --- 1) seed synthetic "prior weeks" PASS reports --------------------------
# We mtime them backwards in 1-day increments so retention can rank them.
for i in $(seq 1 "$PRIOR_PASS"); do
  fname=$(printf '20260%03dT120000Z.json' "$i")
  cat > "$REPORT_DIR/$fname" <<JSON
{"schema_version":1,"result":"PASS","reason":"ok","backup_dir":"/synthetic","backup_file":"/synthetic/x.dump.age","manifest_verified":true,"isolated_project":"casino_bot_restore_synthetic_$i","started_at_utc":"2026-04-${i}T00:00:00Z","ended_at_utc":"2026-04-${i}T00:01:00Z","duration_seconds":60,"verify_seconds":1,"restore_seconds":59,"host_header":"api.example.com","compose_file":"docker-compose.restore.yml","env_file":".env.restore.example"}
JSON
  # Push mtime so the seeded reports look older than the loop reports.
  age_seconds=$(( i * 86400 ))
  touch -d "@$(($(date +%s) - age_seconds))" "$REPORT_DIR/$fname"
done

# --- 2) loop the drill ----------------------------------------------------
echo "-- running drill loop --"
loop_fail=0
loop_reports_seen=0
for n in $(seq 1 "$ITERATIONS"); do
  echo "  iteration $n/$ITERATIONS"
  set +e
  BACKUP_DIR="$BACKUP_DIR" REPORT_DIR="$REPORT_DIR" \
    ./scripts/ops/scheduled_restore_drill.sh > "$OUT_DIR/drill_$n.log" 2>&1
  rc=$?
  set -e
  # No-backup path is expected to exit 2 with a FAIL report on disk.
  if [[ "$rc" != "2" ]]; then
    echo "    FAIL: iteration $n exited $rc (expected 2 on empty backup dir)"
    loop_fail=$((loop_fail + 1))
  fi
  # The drill writes one report per invocation; each filename is a UTC
  # second-resolution timestamp, so sleep 1s to avoid collisions.
  sleep 1
done

# Recount and sanity-check report shapes.
shopt -s nullglob
all_reports=("$REPORT_DIR"/*.json)
shopt -u nullglob
loop_reports_seen=${#all_reports[@]}

echo "-- generated $loop_reports_seen reports total ($PRIOR_PASS prior + $ITERATIONS new)"
expected_total=$(( PRIOR_PASS + ITERATIONS ))
if [[ "$loop_reports_seen" != "$expected_total" ]]; then
  echo "FAIL: expected $expected_total reports, got $loop_reports_seen" >&2
  loop_fail=$((loop_fail + 1))
fi

if ! python3 - "$REPORT_DIR" <<'PY'
import json
import os
import sys

report_dir = sys.argv[1]
required = {
    "schema_version",
    "result",
    "reason",
    "backup_dir",
    "backup_file",
    "manifest_verified",
    "isolated_project",
    "started_at_utc",
    "ended_at_utc",
    "duration_seconds",
}
bad = []
for name in sorted(os.listdir(report_dir)):
    if not name.endswith(".json"):
        continue
    p = os.path.join(report_dir, name)
    try:
        doc = json.loads(open(p).read())
    except Exception as exc:
        bad.append(f"{name}: not JSON ({exc})")
        continue
    missing = required - doc.keys()
    if missing:
        bad.append(f"{name}: missing fields {sorted(missing)}")
    if doc.get("result") not in ("PASS", "FAIL"):
        bad.append(f"{name}: result not PASS/FAIL ({doc.get('result')!r})")
if bad:
    for b in bad:
        print(f"FAIL: {b}", file=sys.stderr)
    sys.exit(1)
PY
then
  echo "FAIL: report shape validation rejected one or more files" >&2
  loop_fail=$((loop_fail + 1))
else
  echo "  ok   all $loop_reports_seen reports are well-formed"
fi

# --- 3) evidence retention against the loop output ------------------------
echo "-- retention dry-run (KEEP_LAST=$KEEP_LAST) --"
REPORT_DIR="$REPORT_DIR" KEEP_LAST="$KEEP_LAST" \
  ./scripts/ops/evidence_retention.sh > "$OUT_DIR/retention_dryrun.out" 2>&1
if ! grep -q -- '--- KEEP ---' "$OUT_DIR/retention_dryrun.out"; then
  echo "FAIL: retention dry-run output missing KEEP section" >&2
  loop_fail=$((loop_fail + 1))
fi

echo "-- retention apply --"
REPORT_DIR="$REPORT_DIR" KEEP_LAST="$KEEP_LAST" APPLY=true \
  ./scripts/ops/evidence_retention.sh > "$OUT_DIR/retention_apply.out" 2>&1

# Post-apply: at most KEEP_LAST PASS reports remain at the top level.
remaining_top=$(find "$REPORT_DIR" -maxdepth 1 -name '*.json' -type f | wc -l)
archived=$(find "$REPORT_DIR/archive" -maxdepth 1 -name '*.json' -type f 2>/dev/null | wc -l)
if [[ "$remaining_top" -gt "$KEEP_LAST" ]]; then
  echo "FAIL: $remaining_top PASS reports remain (expected <= $KEEP_LAST)" >&2
  loop_fail=$((loop_fail + 1))
else
  echo "  ok   $remaining_top PASS reports remain (<= KEEP_LAST=$KEEP_LAST)"
fi
echo "  archived FAIL reports: $archived"

# --- 4) summary -----------------------------------------------------------
echo
echo "== summary =="
echo "  iterations:        $ITERATIONS"
echo "  total reports:     $loop_reports_seen"
echo "  remaining top-lvl: $remaining_top"
echo "  archived FAIL:     $archived"
echo "  output:            $OUT_DIR"

if [[ "$loop_fail" -gt 0 ]]; then
  echo "FAIL: loop validation"
  exit 2
fi
echo "PASS: loop validation"
