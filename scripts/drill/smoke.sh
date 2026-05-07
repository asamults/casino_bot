#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_cmd curl
require_cmd python

echo "Smoke: $API_BASE_URL/health /ready /metrics"

read -r s0 rid0 < <(http_status_and_request_id "$API_BASE_URL/health")
[[ "$s0" == "200" ]] || fail "/health expected 200, got $s0 (request_id=$rid0)"

read -r s1 rid1 < <(http_status_and_request_id "$API_BASE_URL/ready")
[[ "$s1" == "200" ]] || fail "/ready expected 200, got $s1 (request_id=$rid1)"

METRICS_TEXT="$(curl -fsS --max-time 5 "$API_BASE_URL/metrics")" python - <<'PY'
import os
txt = os.environ.get("METRICS_TEXT", "")
required = [
  "casino_bot_http_requests_total",
  "casino_bot_http_request_duration_seconds",
  "casino_bot_db_ready_state",
]
missing = [m for m in required if m not in txt]
if missing:
    raise SystemExit("FAIL: missing metrics: " + ", ".join(missing))
print("OK: baseline metrics present")
PY

pass "smoke OK (request_id_ready=$rid1)"

