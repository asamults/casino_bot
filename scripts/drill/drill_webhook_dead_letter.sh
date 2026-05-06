#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

require_cmd docker
require_cmd curl
require_cmd python

echo "Runbook: docs/runbooks/webhook-dead-letter.md"

require_port_free_or_expected_api 8000 "$API_BASE_URL/health"
compose up -d --build >/dev/null
wait_http_ok "$API_BASE_URL/health" 40 || fail "API did not become healthy"

provider="stripe"
attempts="${BILLING_DEAD_LETTER_ATTEMPTS:-5}"
token="${DRILL_SUPERADMIN_TOKEN:-}"

[[ -n "$token" ]] || fail "set DRILL_SUPERADMIN_TOKEN in your shell/.env for this drill"

# Enable signature verification for local drill.
export STRIPE_WEBHOOK_SECRET="${STRIPE_WEBHOOK_SECRET:-drill_stripe_secret}"
compose up -d --no-deps --force-recreate api >/dev/null
wait_http_ok "$API_BASE_URL/health" 40 || fail "API did not restart with webhook secret"

external_event_id="evt_drill_$(date +%s)"
payload="$(python - "$external_event_id" <<'PY'
import json, sys, time
eid = sys.argv[1]
now = int(time.time())
obj = {
  "id": "sub_drill_1",
  "customer": "cus_drill_missing_user",
  "status": "active",
  "cancel_at_period_end": False,
  "current_period_end": now + 86400,
  "items": {"data": [{"price": {"lookup_key": "test_plan"}}]},
  "metadata": {"user_id": "999999"},
}
print(json.dumps({
  "id": eid,
  "type": "customer.subscription.updated",
  "created": now,
  "data": {"object": obj},
}))
PY
)"

sig_header="$(python - "$STRIPE_WEBHOOK_SECRET" "$payload" <<'PY'
import hashlib, hmac, sys, time
secret = sys.argv[1].encode()
body = sys.argv[2].encode()
ts = str(int(time.time()))
signed = (ts + "." + body.decode()).encode()
sig = hmac.new(secret, signed, hashlib.sha256).hexdigest()
print(f"t={ts},v1={sig}")
PY
)"

echo "Creating a webhook event that will fail mapping (so it can be replayed to dead-letter)..."
resp_headers="$(mktemp)"
status="$(curl -sS -o /dev/null -D "$resp_headers" -w "%{http_code}" \
  -H "Stripe-Signature: $sig_header" \
  -H "Content-Type: application/json" \
  --data "$payload" \
  "$API_BASE_URL/api/v1/billing/webhooks/$provider")"

rid="$(python - "$resp_headers" <<'PY'
import sys
p = sys.argv[1]
rid = "-"
for line in open(p, "r", encoding="utf-8", errors="ignore").read().splitlines():
    if line.lower().startswith("x-request-id:"):
        rid = line.split(":",1)[1].strip() or "-"
print(rid)
PY
)"
rm -f "$resp_headers"

[[ "$status" == "200" || "$status" == "500" ]] || fail "unexpected webhook status=$status (request_id=$rid)"

echo "Replaying failed events until dead-letter..."
for _ in $(seq 1 "$attempts"); do
  curl -fsS --max-time 10 \
    -H "Authorization: Bearer $token" \
    -X POST \
    "$API_BASE_URL/api/v1/admin/billing/events/replay-failed?provider=$provider&limit=50" >/dev/null
  sleep 0.5
done

echo "Checking admin listing (dead_letter=true)..."
dead_letter_total="$(curl -fsS --max-time 10 \
  -H "Authorization: Bearer $token" \
  "$API_BASE_URL/api/v1/admin/billing/events?provider=$provider&dead_letter=true&limit=200" | python - <<'PY'
import json, sys
body = json.loads(sys.stdin.read() or "{}")
print(int(body.get("total") or 0))
PY
)"

[[ "$dead_letter_total" -ge 1 ]] || fail "expected at least 1 dead-lettered event in admin listing, got total=$dead_letter_total"

v="$(metric_value casino_bot_webhook_dead_letter_total)"
[[ -n "$v" ]] || fail "expected metric casino_bot_webhook_dead_letter_total to exist"

pass "webhook_dead_letter drill OK (request_id=$rid; dead_letter_total=$dead_letter_total)"

