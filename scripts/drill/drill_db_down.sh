#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_cmd docker
require_cmd curl
require_cmd python

echo "Runbook: docs/runbooks/db-readiness-failure.md"

require_port_free_or_expected_api 8000 "$API_BASE_URL/health"
compose up -d --build >/dev/null
wait_http_ok "$API_BASE_URL/health" 40 || fail "API did not become healthy"

read -r s0 rid0 < <(http_status_and_request_id "$API_BASE_URL/ready")
[[ "$s0" == "200" ]] || fail "/ready expected 200 before drill, got $s0 (request_id=$rid0)"

echo "Stopping Postgres to simulate outage..."
compose stop postgres >/dev/null
sleep 2

read -r s1 rid1 < <(http_status_and_request_id "$API_BASE_URL/ready")
[[ "$s1" == "503" ]] || fail "/ready expected 503 when DB down, got $s1 (request_id=$rid1)"

v="$(metric_value casino_bot_db_ready_state)"
[[ "$v" == "0" || "$v" == "0.0" ]] || fail "metric casino_bot_db_ready_state expected 0, got ${v:-<missing>}"

echo "Restarting Postgres..."
compose start postgres >/dev/null

echo "Waiting for recovery..."
wait_http_ok "$API_BASE_URL/ready" 60 || fail "API did not recover readiness"

v2="$(metric_value casino_bot_db_ready_state)"
[[ "$v2" == "1" || "$v2" == "1.0" ]] || fail "metric casino_bot_db_ready_state expected 1, got ${v2:-<missing>}"

pass "db_down drill OK (request_id_not_ready=$rid1)"

