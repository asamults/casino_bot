#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-https://api.example.com}"
HOST_HEADER="${HOST_HEADER:-api.example.com}"
METRICS_BASIC_AUTH="${METRICS_BASIC_AUTH:-}"
INSECURE_TLS="${INSECURE_TLS:-false}"

curl_common=(-sS -D - -o /dev/null --max-time 10)
if [[ "$INSECURE_TLS" == "true" ]]; then
  curl_common+=(-k)
fi

echo "== Production preflight =="
echo "BASE_URL=$BASE_URL"
echo "HOST_HEADER=$HOST_HEADER"

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

echo "-- Probes (via proxy/domain) --"
echo "GET /health"
curl "${curl_common[@]}" -H "Host: ${HOST_HEADER}" "${BASE_URL}/health" | grep -q " 200 " || {
  echo "FAIL: /health not 200"
  exit 2
}

echo "GET /ready"
curl "${curl_common[@]}" -H "Host: ${HOST_HEADER}" "${BASE_URL}/ready" | grep -q " 200 " || {
  echo "FAIL: /ready not 200"
  exit 2
}

echo "-- /metrics policy --"
if [[ -z "${METRICS_BASIC_AUTH}" ]]; then
  echo "SKIP: METRICS_BASIC_AUTH not set; only checking that /metrics is not publicly accessible is not possible."
else
  echo "GET /metrics (no auth) should be blocked (401/403)"
  code=$(curl -sS -o /dev/null -w "%{http_code}" "${curl_common[@]}" -H "Host: ${HOST_HEADER}" "${BASE_URL}/metrics" || true)
  if [[ "$code" != "401" && "$code" != "403" ]]; then
    echo "FAIL: /metrics without auth expected 401/403, got ${code}"
    exit 2
  fi

  echo "GET /metrics (with basic auth) should be 200"
  code=$(curl -sS -o /dev/null -w "%{http_code}" "${curl_common[@]}" -u "${METRICS_BASIC_AUTH}" -H "Host: ${HOST_HEADER}" "${BASE_URL}/metrics" || true)
  if [[ "$code" != "200" ]]; then
    echo "FAIL: /metrics with auth expected 200, got ${code}"
    exit 2
  fi
fi

echo "-- Legacy deprecation headers --"
hdrs=$(curl -sS -D - -o /dev/null "${curl_common[@]}" -H "Host: ${HOST_HEADER}" "${BASE_URL}/admin/ping" || true)
echo "$hdrs" | grep -qi "^Deprecation: true" || {
  echo "FAIL: expected Deprecation header on legacy /admin/*"
  exit 2
}
echo "$hdrs" | grep -qi "^Sunset:" || {
  echo "FAIL: expected Sunset header on legacy /admin/*"
  exit 2
}

echo "PASS: production preflight checks ok"

