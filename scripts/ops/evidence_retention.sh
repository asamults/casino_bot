#!/usr/bin/env bash
# evidence_retention.sh — retention discipline for operational evidence
# (M5W4).
#
# Operates on the JSON drill reports produced by
# scripts/ops/scheduled_restore_drill.sh under
# artifacts/reports/restore-drills/.
#
# Policy:
#   - PASS reports: keep the newest KEEP_LAST (default 14). Older PASS
#     reports are deleted.
#   - FAIL reports: never deleted by this script. They are *moved* into
#     artifacts/reports/restore-drills/archive/ on first run so they're
#     out of the way of "list newest 14" queries but still preserved
#     for incident review.
#
# Inputs (env):
#   REPORT_DIR    default: artifacts/reports/restore-drills
#   KEEP_LAST     default: 14
#   APPLY         true|false (default: false → dry-run)
#
# Exit codes:
#   0  ok
#   2  bad input
#
# This script is intentionally separate from backup_retention.sh because
# the policies differ: backups age out by date buckets; evidence ages out
# by count and by status.

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

REPORT_DIR="${REPORT_DIR:-$ROOT_DIR/artifacts/reports/restore-drills}"
KEEP_LAST="${KEEP_LAST:-14}"
APPLY="${APPLY:-false}"

case "$APPLY" in
  true|false) ;;
  *) echo "FAIL: APPLY must be 'true' or 'false', got: $APPLY" >&2; exit 2 ;;
esac
if ! [[ "$KEEP_LAST" =~ ^[0-9]+$ ]]; then
  echo "FAIL: KEEP_LAST must be a non-negative integer, got: $KEEP_LAST" >&2
  exit 2
fi

ARCHIVE_DIR="$REPORT_DIR/archive"
mkdir -p "$REPORT_DIR" "$ARCHIVE_DIR"

echo "== evidence_retention =="
echo "Report dir:   $REPORT_DIR"
echo "Archive dir:  $ARCHIVE_DIR"
echo "Keep last:    $KEEP_LAST (PASS reports)"
echo "Apply:        $APPLY"

shopt -s nullglob
reports=("$REPORT_DIR"/*.json)
shopt -u nullglob

if [[ "${#reports[@]}" -eq 0 ]]; then
  echo "(no reports found; nothing to do)"
  exit 0
fi

# Classify each report (PASS/FAIL) using python (jq may not be installed).
TMP_INPUT="$(mktemp)"
trap 'rm -f "$TMP_INPUT"' EXIT

for f in "${reports[@]}"; do
  mtime=$(stat -c '%Y' "$f" 2>/dev/null || stat -f '%m' "$f")
  printf '%s\t%s\n' "$mtime" "$f" >> "$TMP_INPUT"
done

PYBIN="$(command -v python3 || command -v python || true)"
if [[ -z "$PYBIN" ]]; then
  echo "FAIL: python3/python not available" >&2
  exit 2
fi

PLAN="$("$PYBIN" - "$KEEP_LAST" "$TMP_INPUT" "$ARCHIVE_DIR" <<'PY'
import json
import os
import sys

keep_last = int(sys.argv[1])
input_path = sys.argv[2]
archive_dir = os.path.realpath(sys.argv[3])

entries = []  # (mtime:int, path:str, result:str)
with open(input_path, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if not line:
            continue
        mtime_s, p = line.split("\t", 1)
        # Skip anything already inside the archive dir.
        if os.path.realpath(p).startswith(archive_dir + os.sep):
            continue
        try:
            with open(p, "r", encoding="utf-8") as rfh:
                doc = json.load(rfh)
        except Exception:
            doc = {}
        result = doc.get("result", "UNKNOWN")
        entries.append((int(mtime_s), p, result))

entries.sort(key=lambda e: e[0], reverse=True)

# Bucket: PASS → kept newest N, older deleted. FAIL/UNKNOWN → archived.
pass_entries = [e for e in entries if e[2] == "PASS"]
nonpass_entries = [e for e in entries if e[2] != "PASS"]

keep = {e[1] for e in pass_entries[:keep_last]}
delete = [e for e in pass_entries[keep_last:]]
archive = nonpass_entries[:]

print("--- KEEP ---")
for mtime, p, r in pass_entries[:keep_last]:
    print(f"{r}\t{p}")
print("--- DELETE ---")
for mtime, p, r in delete:
    print(f"{r}\t{p}")
print("--- ARCHIVE ---")
for mtime, p, r in archive:
    print(f"{r}\t{p}")
PY
)"

echo
echo "$PLAN"

if [[ "$APPLY" != "true" ]]; then
  echo
  echo "(dry-run) re-run with APPLY=true to delete old PASS reports and archive non-PASS reports."
  exit 0
fi

echo
echo "== apply =="
deleted=0
archived=0

while IFS=$'\t' read -r _result path; do
  [[ -n "${path:-}" && -e "$path" ]] || continue
  rm -f -- "$path"
  echo "  deleted  $path"
  deleted=$((deleted + 1))
done < <(awk '/^--- DELETE ---/{flag=1;next} /^--- /{flag=0} flag' <<<"$PLAN")

while IFS=$'\t' read -r _result path; do
  [[ -n "${path:-}" && -e "$path" ]] || continue
  mv -- "$path" "$ARCHIVE_DIR/"
  echo "  archived $path -> $ARCHIVE_DIR/"
  archived=$((archived + 1))
done < <(awk '/^--- ARCHIVE ---/{flag=1;next} /^--- /{flag=0} flag' <<<"$PLAN")

echo "PASS: deleted=$deleted archived=$archived"
