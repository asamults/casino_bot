#!/usr/bin/env bash
# production_preflight.sh — pre-cutover smoke against an "external"
# stack reachable over HTTPS (staging or prod). Fails closed.
#
# Inputs (env):
#   BASE_URL            default: https://api.example.com
#   HOST_HEADER         default: api.example.com
#   METRICS_BASIC_AUTH  user:pass for /metrics; required unless METRICS_PUBLIC=true
#   METRICS_PUBLIC      true|false (default: false). If true, /metrics is
#                       allowed to be public (e.g. behind a private network);
#                       the script will only verify that GET /metrics is 200.
#   INSECURE_TLS        true|false (default: false). Pass -k to curl for
#                       self-signed certs (staging).
#   CORS_TEST_ORIGIN    Origin header to use for the CORS preflight check
#                       (default: empty = derive from CORS_ALLOW_ORIGINS env;
#                       if neither is set the CORS check is SKIPPED).
#   LEGACY_ENDPOINTS    comma-separated list of legacy paths expected to emit
#                       Deprecation/Sunset headers. Default: /admin/ping.
#
# Exit codes:
#   0 PASS
#   2 FAIL (any required check)

set -Eeuo pipefail

BASE_URL="${BASE_URL:-https://api.example.com}"
HOST_HEADER="${HOST_HEADER:-api.example.com}"
METRICS_BASIC_AUTH="${METRICS_BASIC_AUTH:-}"
METRICS_PUBLIC="${METRICS_PUBLIC:-false}"
INSECURE_TLS="${INSECURE_TLS:-false}"
CORS_TEST_ORIGIN="${CORS_TEST_ORIGIN:-}"
LEGACY_ENDPOINTS="${LEGACY_ENDPOINTS:-/admin/ping}"

curl_common=(-sS --max-time 10)
if [[ "$INSECURE_TLS" == "true" ]]; then
  curl_common+=(-k)
fi

# Print only the HTTP status code for a request.
curl_status() {
  curl "${curl_common[@]}" -o /dev/null -w "%{http_code}" "$@"
}

# Print just the response headers (-D - and discard body).
curl_headers() {
  curl "${curl_common[@]}" -D - -o /dev/null "$@"
}

echo "== Production preflight =="
echo "BASE_URL=$BASE_URL"
echo "HOST_HEADER=$HOST_HEADER"

# --- 1) required env vars ---------------------------------------------------
required_env=(
  ENVIRONMENT
  DATABASE_URL
  SECRET_KEY
  JWT_SIGNING_KEY
  REFRESH_TOKEN_PEPPER
  USER_API_INTERNAL_TOKEN
  CORS_ALLOW_ORIGINS
  ALLOWED_HOSTS
  BILLING_ALLOWED_RETURN_HOSTS
)

echo "-- Checking required env vars present --"
missing=0
for k in "${required_env[@]}"; do
  if [[ -z "${!k:-}" ]]; then
    echo "MISSING: $k"
    missing=1
  fi
done
if [[ "$missing" == "1" ]]; then
  echo "FAIL: missing required env vars"
  exit 2
fi

if [[ "${ENVIRONMENT}" != "production" ]]; then
  echo "FAIL: ENVIRONMENT must be production (got: ${ENVIRONMENT})"
  exit 2
fi

echo "-- Validating env contract --"
python scripts/validate_env_contract.py --env-file /dev/null

# --- 2) liveness / readiness ------------------------------------------------
echo "-- Probes (via proxy/domain) --"
echo "GET /health"
code=$(curl_status -H "Host: ${HOST_HEADER}" "${BASE_URL}/health")
if [[ "$code" != "200" ]]; then
  echo "FAIL: /health expected 200, got ${code}"
  exit 2
fi

echo "GET /ready"
code=$(curl_status -H "Host: ${HOST_HEADER}" "${BASE_URL}/ready")
if [[ "$code" != "200" ]]; then
  echo "FAIL: /ready expected 200, got ${code}"
  exit 2
fi

# --- 3) CORS preflight (M6W1) ----------------------------------------------
# Resolve the Origin we'll preflight with. Priority:
#   1) explicit CORS_TEST_ORIGIN env
#   2) first entry from CORS_ALLOW_ORIGINS (env value is JSON list)
#   3) skip with a warning
echo "-- CORS preflight (OPTIONS) --"
preflight_origin="$CORS_TEST_ORIGIN"
if [[ -z "$preflight_origin" && -n "${CORS_ALLOW_ORIGINS:-}" ]]; then
  preflight_origin="$(
    python3 -c 'import json,os,sys
v=os.environ.get("CORS_ALLOW_ORIGINS","")
try:
    arr=json.loads(v)
    if isinstance(arr,list) and arr:
        print(arr[0])
except Exception:
    pass
'
  )"
fi
if [[ -z "$preflight_origin" ]]; then
  echo "SKIP: no CORS_TEST_ORIGIN and CORS_ALLOW_ORIGINS not parseable; skipping CORS preflight."
else
  echo "OPTIONS /api/v1/admin/me   (Origin: $preflight_origin)"
  hdrs=$(curl_headers \
      -X OPTIONS \
      -H "Host: ${HOST_HEADER}" \
      -H "Origin: ${preflight_origin}" \
      -H "Access-Control-Request-Method: GET" \
      -H "Access-Control-Request-Headers: Authorization,Content-Type" \
      "${BASE_URL}/api/v1/admin/me" || true)
  # Status line (HTTP/x.y NNN); preflight should be 200 or 204.
  status_line=$(echo "$hdrs" | head -n1 | tr -d '\r')
  case "$status_line" in
    *" 200 "*|*" 204 "*) ;;
    *)
      echo "FAIL: CORS preflight expected 200/204, got: $status_line"
      exit 2
      ;;
  esac
  if ! echo "$hdrs" | grep -qi "^Access-Control-Allow-Origin:"; then
    echo "FAIL: CORS preflight missing Access-Control-Allow-Origin header"
    exit 2
  fi
  if ! echo "$hdrs" | grep -qi "^Access-Control-Allow-Methods:"; then
    echo "FAIL: CORS preflight missing Access-Control-Allow-Methods header"
    exit 2
  fi
  # The allow-origin must echo back the Origin we sent (browsers reject "*"
  # for credentialed requests).
  acao=$(echo "$hdrs" | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}' | tr -d '\r' | head -n1)
  if [[ "$acao" != "$preflight_origin" && "$acao" != "*" ]]; then
    echo "FAIL: Access-Control-Allow-Origin '$acao' does not match Origin '$preflight_origin'"
    exit 2
  fi
fi

# --- 4) /metrics policy (M6W1: stricter) -----------------------------------
# Default policy: production must gate /metrics behind basic auth. If
# METRICS_PUBLIC=true is explicitly opted in (e.g. metrics behind a
# private network), only verify reachability. If neither is set, fail.
echo "-- /metrics policy --"
if [[ "$METRICS_PUBLIC" == "true" ]]; then
  echo "policy: METRICS_PUBLIC=true"
  code=$(curl_status -H "Host: ${HOST_HEADER}" "${BASE_URL}/metrics")
  if [[ "$code" != "200" ]]; then
    echo "FAIL: /metrics (public) expected 200, got ${code}"
    exit 2
  fi
elif [[ -n "${METRICS_BASIC_AUTH}" ]]; then
  echo "policy: basic auth required"
  code=$(curl_status -H "Host: ${HOST_HEADER}" "${BASE_URL}/metrics")
  if [[ "$code" != "401" && "$code" != "403" ]]; then
    echo "FAIL: /metrics without auth expected 401/403, got ${code}"
    exit 2
  fi
  code=$(curl_status -u "${METRICS_BASIC_AUTH}" -H "Host: ${HOST_HEADER}" "${BASE_URL}/metrics")
  if [[ "$code" != "200" ]]; then
    echo "FAIL: /metrics with auth expected 200, got ${code}"
    exit 2
  fi
else
  echo "FAIL: /metrics policy not specified."
  echo "      Set METRICS_BASIC_AUTH=user:pass to require auth (default for prod),"
  echo "      or METRICS_PUBLIC=true to opt out (e.g. metrics behind a private VPC)."
  exit 2
fi

# --- 5) Legacy deprecation headers (M6W1: multi-endpoint) ------------------
echo "-- Legacy deprecation headers --"
IFS=',' read -ra _legacy_paths <<< "$LEGACY_ENDPOINTS"
for path in "${_legacy_paths[@]}"; do
  path="${path## }"; path="${path%% }"
  [[ -z "$path" ]] && continue
  echo "GET ${path}"
  hdrs=$(curl_headers -H "Host: ${HOST_HEADER}" "${BASE_URL}${path}" || true)
  if ! echo "$hdrs" | grep -qi "^Deprecation: true"; then
    echo "FAIL: missing 'Deprecation: true' header on ${path}"
    exit 2
  fi
  if ! echo "$hdrs" | grep -qi "^Sunset:"; then
    echo "FAIL: missing 'Sunset:' header on ${path}"
    exit 2
  fi
  if ! echo "$hdrs" | grep -qi '^Link:.*rel="successor-version"'; then
    echo "WARN: 'Link: ...; rel=\"successor-version\"' missing on ${path}"
  fi
done

echo "PASS: production preflight checks ok"
