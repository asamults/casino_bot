#!/usr/bin/env bash
# backup_retention.sh — apply (or preview) the documented backup retention
# policy to encrypted backup artifacts.
#
# Policy (defaults, see docs/ops/backup-retention-policy.md):
#   daily:   keep last 7 distinct UTC dates
#   weekly:  keep 1 backup from each of the last 4 ISO weeks
#   monthly: keep 1 backup from each of the last 3 calendar months
#
# Anything outside the union of {daily, weekly, monthly} keepers is a
# "delete candidate". By default this script only PREVIEWS deletions
# (dry-run). Pass APPLY=true to actually remove files (and their
# .sha256 / .meta.json sidecars).
#
# Inputs:
#   BACKUP_DIR       directory of encrypted backups   (default: ./backups)
#   APPLY            true | false                     (default: false)
#   DAILY_KEEP       int                              (default: 7)
#   WEEKLY_KEEP      int                              (default: 4)
#   MONTHLY_KEEP     int                              (default: 3)
#
# Selection rules:
#   - We only consider files matching *.dump.age and *.dump.gpg.
#   - Each artifact is bucketed by the mtime of the encrypted file.
#   - For weekly / monthly buckets we keep the *newest* backup in each
#     bucket (deterministic, "the last one of the week/month survives").
#   - Sidecars (.sha256, .meta.json) follow their parent: kept iff parent
#     is kept; deleted iff parent is deleted.
#
# Exit codes:
#   0  ok
#   2  bad input
#   3  unexpected I/O failure during apply

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/backups}"
APPLY="${APPLY:-false}"
DAILY_KEEP="${DAILY_KEEP:-7}"
WEEKLY_KEEP="${WEEKLY_KEEP:-4}"
MONTHLY_KEEP="${MONTHLY_KEEP:-3}"

if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "FAIL: BACKUP_DIR not a directory: $BACKUP_DIR" >&2
  exit 2
fi

case "$APPLY" in
  true|false) ;;
  *) echo "FAIL: APPLY must be 'true' or 'false', got: $APPLY" >&2; exit 2 ;;
esac

for v in DAILY_KEEP WEEKLY_KEEP MONTHLY_KEEP; do
  if ! [[ "${!v}" =~ ^[0-9]+$ ]]; then
    echo "FAIL: $v must be a non-negative integer, got: ${!v}" >&2
    exit 2
  fi
done

echo "== backup_retention =="
echo "Dir:           $BACKUP_DIR"
echo "Apply:         $APPLY"
echo "Daily keep:    $DAILY_KEEP"
echo "Weekly keep:   $WEEKLY_KEEP"
echo "Monthly keep:  $MONTHLY_KEEP"

# --- list candidate artifacts (no globbing surprises on empty dir) -------
shopt -s nullglob
artifacts=("$BACKUP_DIR"/*.dump.age "$BACKUP_DIR"/*.dump.gpg)
shopt -u nullglob

if [[ "${#artifacts[@]}" -eq 0 ]]; then
  echo "(no encrypted artifacts found; nothing to do)"
  exit 0
fi

# --- compute keep / delete sets in Python (clearer than awk) ------------
# Input lines: <mtime_epoch>\t<path>
TMP_INPUT="$(mktemp)"
trap 'rm -f "$TMP_INPUT"' EXIT

for f in "${artifacts[@]}"; do
  mtime="$(stat -c '%Y' "$f" 2>/dev/null || stat -f '%m' "$f")"
  printf '%s\t%s\n' "$mtime" "$f" >> "$TMP_INPUT"
done

# `python3` may not always be on PATH on minimal hosts; fallback to `python`.
PYBIN="$(command -v python3 || command -v python || true)"
if [[ -z "$PYBIN" ]]; then
  echo "FAIL: neither python3 nor python is available" >&2
  exit 2
fi

# Output: two sections separated by --- KEEP/DELETE markers.
PLAN="$("$PYBIN" - "$DAILY_KEEP" "$WEEKLY_KEEP" "$MONTHLY_KEEP" "$TMP_INPUT" <<'PY'
import datetime as dt
import sys

daily_keep, weekly_keep, monthly_keep, path = (
    int(sys.argv[1]),
    int(sys.argv[2]),
    int(sys.argv[3]),
    sys.argv[4],
)

entries = []  # list of (mtime_epoch:int, path:str, dt_utc:datetime)
with open(path, "r", encoding="utf-8") as fh:
    for line in fh:
        line = line.rstrip("\n")
        if not line:
            continue
        mtime_s, p = line.split("\t", 1)
        ts = int(mtime_s)
        entries.append((ts, p, dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)))

# Newest first.
entries.sort(key=lambda e: e[0], reverse=True)

keep = set()

# Daily: keep the newest backup per UTC date, up to N most-recent dates.
seen_days = []
day_winner = {}
for ts, p, d in entries:
    key = d.strftime("%Y-%m-%d")
    if key not in day_winner:
        day_winner[key] = p
        seen_days.append(key)
    if len(seen_days) >= daily_keep:
        # We still want to record winners for already-seen days,
        # so don't break: continue to fill day_winner for those days.
        pass
for key in seen_days[:daily_keep]:
    keep.add(day_winner[key])

# Weekly: ISO week (year, week). Keep newest per (year, week), up to N.
seen_weeks = []
week_winner = {}
for ts, p, d in entries:
    iso_year, iso_week, _ = d.isocalendar()
    key = (iso_year, iso_week)
    if key not in week_winner:
        week_winner[key] = p
        seen_weeks.append(key)
for key in seen_weeks[:weekly_keep]:
    keep.add(week_winner[key])

# Monthly: keep newest per (year, month), up to N.
seen_months = []
month_winner = {}
for ts, p, d in entries:
    key = (d.year, d.month)
    if key not in month_winner:
        month_winner[key] = p
        seen_months.append(key)
for key in seen_months[:monthly_keep]:
    keep.add(month_winner[key])

print("--- KEEP ---")
for ts, p, d in entries:
    if p in keep:
        print(f"{d.strftime('%Y-%m-%dT%H:%M:%SZ')}\t{p}")
print("--- DELETE ---")
for ts, p, d in entries:
    if p not in keep:
        print(f"{d.strftime('%Y-%m-%dT%H:%M:%SZ')}\t{p}")
PY
)"

echo
echo "$PLAN"

# --- apply phase ---------------------------------------------------------
if [[ "$APPLY" != "true" ]]; then
  echo
  echo "(dry-run) re-run with APPLY=true to actually delete the files above."
  exit 0
fi

echo
echo "== apply (deleting non-kept artifacts + sidecars) =="
deleted=0
while IFS=$'\t' read -r _ts path; do
  [[ -n "${path:-}" && -e "$path" ]] || continue
  for sidecar in "$path" "$path.sha256" "$path.meta.json"; do
    if [[ -e "$sidecar" ]]; then
      rm -f -- "$sidecar"
      echo "  deleted $sidecar"
      deleted=$((deleted + 1))
    fi
  done
done < <(awk '/^--- DELETE ---/{flag=1;next} /^--- /{flag=0} flag' <<<"$PLAN")

echo "PASS: deleted $deleted files"
