#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.prod.example}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
HOST_HEADER="${HOST_HEADER:-api.example.com}"
DURATION_SECONDS="${DURATION_SECONDS:-300}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-1}"

echo "Soak harness: scripts/soak/soak_http.py"
echo "Env: $ENV_FILE"
echo "Compose: $COMPOSE_FILE"
echo "Host header: $HOST_HEADER"
echo "Duration: ${DURATION_SECONDS}s interval=${INTERVAL_SECONDS}s"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

echo "Waiting for /ready to become 200..."
docker exec casino_bot-api bash -lc "python - <<'PY'
import os, time, urllib.request
host=os.environ.get('HOST_HEADER','api.example.com')
deadline=time.time()+60
while True:
    try:
        req=urllib.request.Request('http://127.0.0.1:8000/ready', headers={'Host':host})
        with urllib.request.urlopen(req, timeout=2) as r:
            if r.status==200:
                print('OK: /ready=200')
                raise SystemExit(0)
    except Exception:
        pass
    if time.time()>deadline:
        print('FAIL: /ready did not become 200 within 60s')
        raise SystemExit(2)
    time.sleep(1)
PY" HOST_HEADER="$HOST_HEADER"

echo "Running soak from inside api container (private-network style)..."
docker exec casino_bot-api bash -lc \
  "SOAK_BASE_URL=http://127.0.0.1:8000 \
   SOAK_HOST_HEADER='$HOST_HEADER' \
   SOAK_DURATION_SECONDS='$DURATION_SECONDS' \
   SOAK_INTERVAL_SECONDS='$INTERVAL_SECONDS' \
   SOAK_METRICS_BASIC_AUTH='${METRICS_BASIC_AUTH:-}' \
   python scripts/soak/soak_http.py --report-json /tmp/soak_report.json"

echo "Report JSON (from container):"
docker exec casino_bot-api bash -lc "cat /tmp/soak_report.json"

