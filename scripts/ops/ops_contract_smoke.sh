#!/usr/bin/env bash
# ops_contract_smoke.sh — fast, no-Docker smoke for the ops tooling
# introduced in M5W3/M5W4. Designed to run in CI as a regression gate
# so that breaking changes to backup/restore/retention scripts surface
# before they hit a real drill.
#
# Coverage:
#   1. verify_backup_manifest.py  — runnable; --help works; PASS on a
#      synthetic encrypted artifact + manifest; FAIL on tampered sha256.
#   2. scheduled_restore_drill.sh — runnable; on an empty BACKUP_DIR it
#      exits 2 and writes a well-formed JSON FAIL report.
#   3. evidence_retention.sh      — dry-run on synthetic fixture lists
#      KEEP/DELETE/ARCHIVE buckets; APPLY=true performs them; FAIL
#      reports are archived (never deleted).
#   4. backup_retention.sh        — dry-run on empty dir is a no-op;
#      invalid APPLY value fails closed.
#
# All work happens inside a per-invocation tempdir; no real backups are
# created or touched. Exit 0 on success, 2 on any contract failure.

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

WORK_DIR="$(mktemp -d -t casino_bot_ops_smoke.XXXXXX)"
cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

PASS_COUNT=0
FAIL_COUNT=0

note() {
  echo
  echo "== $* =="
}

ok() {
  echo "  ok   $*"
  PASS_COUNT=$((PASS_COUNT + 1))
}

bad() {
  echo "  FAIL $*" >&2
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

require_python() {
  command -v python3 >/dev/null 2>&1 \
    || { echo "FAIL: python3 required for ops smoke"; exit 2; }
}
require_python

# ---------------------------------------------------------------------------
# 1) verify_backup_manifest.py
# ---------------------------------------------------------------------------
note "verify_backup_manifest.py"

if python3 scripts/ops/verify_backup_manifest.py --help >/dev/null 2>&1; then
  ok "--help"
else
  bad "--help failed"
fi

# Build a synthetic v2 manifest + encrypted artifact + sidecar.
SAMPLE_DIR="$WORK_DIR/manifest"
mkdir -p "$SAMPLE_DIR"
SAMPLE_BASENAME="casino_bot_synthetic.dump.age"
SAMPLE_PAYLOAD="ops contract smoke synthetic payload"
echo -n "$SAMPLE_PAYLOAD" > "$SAMPLE_DIR/$SAMPLE_BASENAME"
SAMPLE_SHA="$(sha256sum "$SAMPLE_DIR/$SAMPLE_BASENAME" | awk '{print $1}')"
echo "$SAMPLE_SHA  $SAMPLE_BASENAME" > "$SAMPLE_DIR/$SAMPLE_BASENAME.sha256"
cat > "$SAMPLE_DIR/$SAMPLE_BASENAME.meta.json" <<JSON
{
  "schema_version": 2,
  "created_at_utc": "2026-05-07T00:00:00Z",
  "tool": "age",
  "encryption": "age",
  "recipient": "age:ops/backup/age-recipients.txt",
  "plaintext_basename": "casino_bot_synthetic.dump",
  "encrypted_basename": "$SAMPLE_BASENAME",
  "plaintext_size_bytes": 100,
  "encrypted_size_bytes": ${#SAMPLE_PAYLOAD},
  "sha256": "$SAMPLE_SHA",
  "compose_file": "docker-compose.prod.yml",
  "env_file": ".env.prod.example",
  "postgres_service": "postgres",
  "git_sha": "abc1234",
  "git_describe": "v0.0.1",
  "postgres_version": "16.11",
  "alembic_revision": "deadbeef"
}
JSON

if python3 scripts/ops/verify_backup_manifest.py "$SAMPLE_DIR/$SAMPLE_BASENAME.meta.json" >/dev/null 2>&1; then
  ok "PASS on valid synthetic manifest"
else
  bad "verifier rejected a valid synthetic manifest"
fi

# Tamper: change the artifact contents so sha256 won't match.
echo -n "tampered" > "$SAMPLE_DIR/$SAMPLE_BASENAME"
if python3 scripts/ops/verify_backup_manifest.py \
    "$SAMPLE_DIR/$SAMPLE_BASENAME.meta.json" >/dev/null 2>&1; then
  bad "verifier passed on tampered artifact"
else
  ok "FAIL on tampered artifact (sha256 mismatch)"
fi

# ---------------------------------------------------------------------------
# 2) scheduled_restore_drill.sh — no-backup path
# ---------------------------------------------------------------------------
note "scheduled_restore_drill.sh (empty BACKUP_DIR)"
DRILL_BACKUPS="$WORK_DIR/empty_backups"
DRILL_REPORTS="$WORK_DIR/drill_reports"
mkdir -p "$DRILL_BACKUPS" "$DRILL_REPORTS"

set +e
BACKUP_DIR="$DRILL_BACKUPS" REPORT_DIR="$DRILL_REPORTS" \
  ./scripts/ops/scheduled_restore_drill.sh >/dev/null 2>&1
drill_rc=$?
set -e

if [[ "$drill_rc" == "2" ]]; then
  ok "exit code 2 on empty BACKUP_DIR"
else
  bad "expected exit 2, got $drill_rc"
fi

# A FAIL report must have been written regardless.
shopt -s nullglob
drill_jsons=("$DRILL_REPORTS"/*.json)
shopt -u nullglob
if [[ "${#drill_jsons[@]}" -ge 1 ]]; then
  ok "FAIL report written ($(basename "${drill_jsons[0]}"))"
else
  bad "no drill report written on no-backup path"
fi

# Validate the JSON shape: result == FAIL, manifest_verified == false.
if [[ "${#drill_jsons[@]}" -ge 1 ]]; then
  if python3 - "${drill_jsons[0]}" <<'PY' >/dev/null 2>&1
import json, sys
doc = json.loads(open(sys.argv[1]).read())
assert doc["result"] == "FAIL", doc
assert doc["manifest_verified"] is False, doc
assert isinstance(doc.get("schema_version"), int), doc
PY
  then
    ok "FAIL report shape is well-formed"
  else
    bad "FAIL report shape is malformed"
  fi
fi

# ---------------------------------------------------------------------------
# 3) evidence_retention.sh — dry-run + apply on synthetic fixture
# ---------------------------------------------------------------------------
note "evidence_retention.sh"
EVID_DIR="$WORK_DIR/evidence"
mkdir -p "$EVID_DIR"

# 3 PASS reports + 1 FAIL report.
for i in 1 2 3; do
  printf '{"result":"PASS","backup_file":"x"}\n' > "$EVID_DIR/2026050${i}T120000Z.json"
done
printf '{"result":"FAIL","reason":"sha256","backup_file":"x"}\n' > "$EVID_DIR/20260504T120000Z.json"

if REPORT_DIR="$EVID_DIR" KEEP_LAST=2 ./scripts/ops/evidence_retention.sh \
    > "$WORK_DIR/retention_dryrun.out" 2>&1; then
  ok "dry-run on synthetic fixture"
else
  bad "dry-run exited non-zero"
  cat "$WORK_DIR/retention_dryrun.out" >&2
fi

if grep -q -- '--- KEEP ---' "$WORK_DIR/retention_dryrun.out" \
   && grep -q -- '--- DELETE ---' "$WORK_DIR/retention_dryrun.out" \
   && grep -q -- '--- ARCHIVE ---' "$WORK_DIR/retention_dryrun.out"; then
  ok "dry-run partitioned KEEP/DELETE/ARCHIVE"
else
  bad "dry-run output missing KEEP/DELETE/ARCHIVE sections"
fi

if REPORT_DIR="$EVID_DIR" KEEP_LAST=2 APPLY=true ./scripts/ops/evidence_retention.sh \
    > "$WORK_DIR/retention_apply.out" 2>&1; then
  ok "apply on synthetic fixture"
else
  bad "apply exited non-zero"
  cat "$WORK_DIR/retention_apply.out" >&2
fi

# Final state assertions.
remaining_pass=$(find "$EVID_DIR" -maxdepth 1 -name '*.json' -type f | wc -l)
archived_fail=$(find "$EVID_DIR/archive" -maxdepth 1 -name '*.json' -type f 2>/dev/null | wc -l)
if [[ "$remaining_pass" == "2" && "$archived_fail" == "1" ]]; then
  ok "post-apply state: 2 PASS kept, 1 FAIL archived"
else
  bad "post-apply state wrong: pass=$remaining_pass archived=$archived_fail"
fi

# Idempotency: re-apply must not change state and must not error.
if REPORT_DIR="$EVID_DIR" KEEP_LAST=2 APPLY=true ./scripts/ops/evidence_retention.sh \
    >/dev/null 2>&1; then
  remaining_pass2=$(find "$EVID_DIR" -maxdepth 1 -name '*.json' -type f | wc -l)
  archived_fail2=$(find "$EVID_DIR/archive" -maxdepth 1 -name '*.json' -type f | wc -l)
  if [[ "$remaining_pass2" == "$remaining_pass" && "$archived_fail2" == "$archived_fail" ]]; then
    ok "second apply is idempotent"
  else
    bad "second apply mutated state"
  fi
else
  bad "second apply errored"
fi

# ---------------------------------------------------------------------------
# 4a) secrets_hygiene_check.sh — runnable; clean on a synthetic empty tree;
#     fails on a synthetic forbidden tree (M6W2).
# ---------------------------------------------------------------------------
note "secrets_hygiene_check.sh (M6W2)"
HYG_CLEAN="$WORK_DIR/hyg_clean"
mkdir -p "$HYG_CLEAN/src"
echo "ok" > "$HYG_CLEAN/src/main.py"
if ROOT="$HYG_CLEAN" ./scripts/ops/secrets_hygiene_check.sh > "$WORK_DIR/hyg_clean.out" 2>&1; then
  ok "clean tree: PASS"
else
  bad "clean tree unexpectedly failed"
  cat "$WORK_DIR/hyg_clean.out" >&2
fi

HYG_DIRTY="$WORK_DIR/hyg_dirty"
mkdir -p "$HYG_DIRTY"
touch "$HYG_DIRTY/.env.prod" "$HYG_DIRTY/db.dump" "$HYG_DIRTY/server.htpasswd"
set +e
ROOT="$HYG_DIRTY" ./scripts/ops/secrets_hygiene_check.sh > "$WORK_DIR/hyg_dirty.out" 2>&1
hyg_rc=$?
set -e
if [[ "$hyg_rc" == "3" ]]; then
  ok "dirty tree: exit 3"
else
  bad "dirty tree expected exit 3, got $hyg_rc"
fi
if grep -q '\.env\.prod' "$WORK_DIR/hyg_dirty.out" \
   && grep -q '\.dump' "$WORK_DIR/hyg_dirty.out" \
   && grep -q '\.htpasswd' "$WORK_DIR/hyg_dirty.out"; then
  ok "dirty tree: all three forbidden paths reported"
else
  bad "dirty tree: violation list missing entries"
  cat "$WORK_DIR/hyg_dirty.out" >&2
fi

# ---------------------------------------------------------------------------
# 4b) htpasswd_gen.sh — runnable; produces a hashed entry; rejects short pwd
# ---------------------------------------------------------------------------
note "htpasswd_gen.sh (M6W2)"
HTP_DIR="$WORK_DIR/htp"
mkdir -p "$HTP_DIR"
HTP_PASS='ContractSmokePassword!1'
if USERNAME=metrics PASSWORD="$HTP_PASS" OUTPUT_FILE="$HTP_DIR/.htpasswd" \
    ./scripts/ops/htpasswd_gen.sh > "$WORK_DIR/htp.out" 2>&1; then
  ok "generates an entry"
else
  bad "htpasswd_gen failed"
  cat "$WORK_DIR/htp.out" >&2
fi
if grep -q "^metrics:" "$HTP_DIR/.htpasswd"; then
  ok "entry starts with metrics:"
else
  bad "no metrics: line in output"
fi
if grep -qF "$HTP_PASS" "$HTP_DIR/.htpasswd"; then
  bad "plaintext password leaked into output"
else
  ok "plaintext password NOT in output"
fi
mode=$(stat -c '%a' "$HTP_DIR/.htpasswd" 2>/dev/null || stat -f '%Lp' "$HTP_DIR/.htpasswd")
if [[ "$mode" == "600" ]]; then
  ok "output mode is 0600"
else
  bad "expected mode 600, got $mode"
fi

set +e
USERNAME=metrics PASSWORD='short' OUTPUT_FILE="$HTP_DIR/.htpasswd_short" \
  ./scripts/ops/htpasswd_gen.sh > "$WORK_DIR/htp_short.out" 2>&1
htp_rc=$?
set -e
if [[ "$htp_rc" == "2" ]]; then
  ok "rejects short password (rc=2)"
else
  bad "short password expected rc=2, got $htp_rc"
fi

# ---------------------------------------------------------------------------
# 5) backup_retention.sh — dry-run on empty + invalid APPLY
# ---------------------------------------------------------------------------
note "backup_retention.sh"
BR_DIR="$WORK_DIR/backups"
mkdir -p "$BR_DIR"

if BACKUP_DIR="$BR_DIR" ./scripts/ops/backup_retention.sh > "$WORK_DIR/br_empty.out" 2>&1; then
  if grep -q "no encrypted artifacts found" "$WORK_DIR/br_empty.out"; then
    ok "empty dir is a clean no-op"
  else
    bad "expected 'no encrypted artifacts found' on empty dir"
  fi
else
  bad "dry-run on empty dir errored"
  cat "$WORK_DIR/br_empty.out" >&2
fi

set +e
BACKUP_DIR="$BR_DIR" APPLY=maybe ./scripts/ops/backup_retention.sh \
  > "$WORK_DIR/br_bad.out" 2>&1
br_rc=$?
set -e
if [[ "$br_rc" == "2" ]]; then
  ok "rejects APPLY=maybe with exit 2"
else
  bad "APPLY=maybe expected rc=2, got $br_rc"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo
echo "== summary =="
echo "  passed: $PASS_COUNT"
echo "  failed: $FAIL_COUNT"
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "FAIL: ops contract smoke"
  exit 2
fi
echo "PASS: ops contract smoke"
