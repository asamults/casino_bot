#!/usr/bin/env bash
# verify_proxy_policies.sh — operational smoke for the reverse-proxy
# access policies (M6W2).
#
# Targets a *running* proxy in front of the casino_bot api and asserts:
#
#   1. /health, /ready are open (no auth required, 200).
#   2. /metrics:
#       - without basic auth -> 401/403,
#       - with valid basic auth -> 200.
#   3. /admin and /api/v1/admin:
#       - from an unlisted IP -> 403 (proxy denies before app),
#       - from an allowlisted IP -> request reaches the app
#         (200/401/403 depending on Authorization header, but NOT a
#         proxy-level 403 with no app body).
#
# This script does NOT spin up a stack; that's the operator's job.
# Point it at staging/prod via BASE_URL.
#
# Inputs (env):
#   BASE_URL              default: http://127.0.0.1:8080
#   HOST_HEADER           Host header to send (optional)
#   METRICS_BASIC_AUTH    user:pass for /metrics
#   ADMIN_ALLOWLIST_PROBE true|false (default: false). When false,
#                         we only verify the *negative* case (unlisted
#                         caller is denied with 403). When true, we
#                         additionally trust that the script is being
#                         run from an allowlisted source IP and verify
#                         the proxy lets the request through (anything
#                         other than 403 is acceptable, since auth is
#                         enforced by the app itself).
#   INSECURE_TLS          true|false (default: false). Pass -k to curl.
#
# Exit codes:
#   0 PASS
#   2 FAIL (any policy violation)

set -Eeuo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
HOST_HEADER="${HOST_HEADER:-}"
METRICS_BASIC_AUTH="${METRICS_BASIC_AUTH:-}"
ADMIN_ALLOWLIST_PROBE="${ADMIN_ALLOWLIST_PROBE:-false}"
INSECURE_TLS="${INSECURE_TLS:-false}"

curl_args=(-sS --max-time 10)
if [[ "$INSECURE_TLS" == "true" ]]; then
  curl_args+=(-k)
fi
if [[ -n "$HOST_HEADER" ]]; then
  curl_args+=(-H "Host: $HOST_HEADER")
fi

# Print only the HTTP status code. A connection-level error (e.g.
# proxy unreachable) is reported as 000 so each individual probe can
# fail independently without `set -e` aborting the rest of the script.
status() {
  local code
  code=$(curl "${curl_args[@]}" -o /dev/null -w "%{http_code}" "$@" 2>/dev/null || true)
  printf '%s' "${code:-000}"
}

PASS=0
FAIL=0
ok()  { echo "  ok   $*"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL $*" >&2; FAIL=$((FAIL + 1)); }

echo "== verify_proxy_policies =="
echo "BASE_URL:    $BASE_URL"
[[ -n "$HOST_HEADER" ]] && echo "HOST_HEADER: $HOST_HEADER"

# --- 1) /health and /ready are open --------------------------------------
echo
echo "-- open probes --"
for path in /health /ready; do
  code=$(status "${BASE_URL}${path}")
  if [[ "$code" == "200" ]]; then
    ok "$path returns 200 without auth"
  else
    bad "$path expected 200, got $code"
  fi
done

# --- 2) /metrics policy ---------------------------------------------------
echo
echo "-- /metrics policy --"
code=$(status "${BASE_URL}/metrics")
case "$code" in
  401|403) ok "/metrics without auth blocked ($code)" ;;
  *)       bad "/metrics without auth expected 401/403, got $code" ;;
esac

if [[ -n "$METRICS_BASIC_AUTH" ]]; then
  code=$(status -u "$METRICS_BASIC_AUTH" "${BASE_URL}/metrics")
  if [[ "$code" == "200" ]]; then
    ok "/metrics with basic auth returns 200"
  else
    bad "/metrics with basic auth expected 200, got $code"
  fi
else
  echo "  SKIP positive case: METRICS_BASIC_AUTH not provided"
fi

# --- 3) /admin and /api/v1/admin --------------------------------------
echo
echo "-- /admin allowlist policy --"
for path in /admin/ping /api/v1/admin/me; do
  code=$(status "${BASE_URL}${path}")
  if [[ "$ADMIN_ALLOWLIST_PROBE" == "true" ]]; then
    # We assume the runner IS allowlisted; the proxy must NOT 403 us.
    # The app may still return 401/200/etc. depending on Authorization;
    # we only assert the proxy didn't deny us at the edge.
    if [[ "$code" == "403" ]]; then
      bad "$path returned 403 from a supposedly-allowlisted source"
    else
      ok "$path proxy allowed (status from app: $code)"
    fi
  else
    # We assume the runner is NOT allowlisted; proxy must 403 us.
    if [[ "$code" == "403" ]]; then
      ok "$path correctly 403'd at the proxy (caller not allowlisted)"
    else
      bad "$path expected 403 from non-allowlisted caller, got $code"
    fi
  fi
done

echo
echo "== summary =="
echo "  passed: $PASS"
echo "  failed: $FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  echo "FAIL: proxy policies"
  exit 2
fi
echo "PASS: proxy policies"
