#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_cmd docker
require_cmd curl
require_cmd python

echo "Runbook: docs/runbooks/ci-gates-failure.md (alerts: 5xx spike examples) / incident template: docs/runbooks/incident-template.md"

require_port_free_or_expected_api 8000 "$API_BASE_URL/health"
compose up -d --build >/dev/null
wait_http_ok "$API_BASE_URL/health" 40 || fail "API did not become healthy"

route="/health"
n="${N_REQUESTS:-10}"

before="$(metric_counter_sum_by_route_and_status casino_bot_http_requests_total "$route" "500")"

echo "Forcing 500 on path=$route for $n requests..."
export DRILL_FORCE_500_ON_PATH="$route"
compose up -d --no-deps --force-recreate api >/dev/null
wait_http_ok "$API_BASE_URL/health" 40 || fail "API did not restart"

last_rid="-"
for _ in $(seq 1 "$n"); do
  read -r st rid < <(http_status_and_request_id "$API_BASE_URL$route")
  last_rid="$rid"
  [[ "$st" == "500" ]] || fail "expected 500 during drill, got $st (request_id=$rid)"
done

after="$(metric_counter_sum_by_route_and_status casino_bot_http_requests_total "$route" "500")"

python - "$before" "$after" "$n" <<'PY'
import sys
before = float(sys.argv[1]); after = float(sys.argv[2]); n = int(sys.argv[3])
delta = after - before
if delta < n:
    raise SystemExit(f"FAIL: expected >= {n} new 500s, got delta={delta}")
print(f"OK: 500 counter delta={delta}")
PY

echo "Disabling forced-500 and restoring service..."
unset DRILL_FORCE_500_ON_PATH
compose up -d --no-deps --force-recreate api >/dev/null
wait_http_ok "$API_BASE_URL/health" 40 || fail "API did not restore after drill"

read -r st2 rid2 < <(http_status_and_request_id "$API_BASE_URL$route")
[[ "$st2" == "200" ]] || fail "expected 200 after drill cleanup, got $st2 (request_id=$rid2)"

pass "5xx_spike drill OK (last_request_id=$last_rid)"

