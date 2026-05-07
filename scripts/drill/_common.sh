#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

pass() {
  echo "PASS: $*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

require_port_free_or_expected_api() {
  local host="127.0.0.1"
  local port="${1:-8000}"
  local url="${2:-$API_BASE_URL/health}"
  python - "$host" "$port" "$url" <<'PY'
import socket, sys, urllib.request
host, port, url = sys.argv[1], int(sys.argv[2]), sys.argv[3]
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.5)
try:
    s.bind((host, port))
    s.close()
    sys.exit(0)
except OSError:
    # Port in use: if casino_bot is already serving, that's fine.
    try:
        with urllib.request.urlopen(url, timeout=1) as r:
            if 200 <= r.status < 300:
                sys.exit(0)
    except Exception:
        pass
    sys.stderr.write(
        f"FAIL: port {port} is already in use and {url} did not respond OK. "
        "Stop the conflicting process/container (e.g. `docker compose down`) or set API_BASE_URL.\n"
    )
    sys.exit(2)
PY
}

compose() {
  docker compose "$@"
}

wait_http_ok() {
  local url="$1"
  local timeout_s="${2:-30}"
  local start
  start="$(date +%s)"
  while true; do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( "$(date +%s)" - start > timeout_s )); then
      return 1
    fi
    sleep 1
  done
}

http_status_and_request_id() {
  local url="$1"
  local headers
  headers="$(curl -sS -o /dev/null -D - --max-time 5 "$url")"
  HTTP_HEADERS="$headers" python - <<'PY'
import os
status = None
rid = "-"
for line in os.environ.get("HTTP_HEADERS", "").splitlines():
    if line.startswith("HTTP/"):
        try:
            status = int(line.split()[1])
        except Exception:
            status = None
    if line.lower().startswith("x-request-id:"):
        rid = line.split(":",1)[1].strip() or "-"
print(f"{status or 0} {rid}")
PY
}

metric_value() {
  local metric_name="$1"
  local metrics_text
  metrics_text="$(curl -fsS --max-time 5 "$API_BASE_URL/metrics")"
  METRICS_TEXT="$metrics_text" python - "$metric_name" <<'PY'
import os, re, sys
name = sys.argv[1]
text = os.environ.get("METRICS_TEXT", "")
pattern = re.compile(rf"^{re.escape(name)}(?:\\{{[^}}]*\\}})?\\s+([0-9eE+\\-.]+)\\s*$", re.M)
m = pattern.search(text)
if not m:
    print("")
    sys.exit(0)
print(m.group(1))
PY
}

metric_counter_sum_by_route_and_status() {
  local metric_name="$1"
  local route="$2"
  local status="$3"
  local metrics_text
  metrics_text="$(curl -fsS --max-time 5 "$API_BASE_URL/metrics")"
  METRICS_TEXT="$metrics_text" python - "$metric_name" "$route" "$status" <<'PY'
import os, sys
name, route, status = sys.argv[1], sys.argv[2], sys.argv[3]
total = 0.0
for line in os.environ.get("METRICS_TEXT", "").splitlines():
    if not line.startswith(name + "{"):
        continue
    if f'route="{route}"' not in line:
        continue
    if f'status="{status}"' not in line:
        continue
    # e.g. metric{...} 12
    try:
        total += float(line.rsplit(" ", 1)[1])
    except Exception:
        pass
print(f"{total}")
PY
}

