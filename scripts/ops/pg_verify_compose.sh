#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env.prod.example}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
HOST_HEADER="${HOST_HEADER:-api.example.com}"

echo "== verify restore (compose) =="
echo "Host header: $HOST_HEADER"

echo "-- waiting for /ready=200 inside api container --"
docker exec casino_bot-api bash -lc "python - <<'PY'
import os, time, urllib.request
host=os.environ.get('HOST_HEADER','api.example.com')
deadline=time.time()+90
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
        print('FAIL: /ready not 200 within 90s')
        raise SystemExit(2)
    time.sleep(1)
PY" HOST_HEADER="$HOST_HEADER"

echo "-- basic probe checks --"
docker exec casino_bot-api bash -lc "python - <<'PY'
import os, urllib.request
host=os.environ.get('HOST_HEADER','api.example.com')
for path in ('/health','/ready','/metrics'):
    req=urllib.request.Request('http://127.0.0.1:8000'+path, headers={'Host':host})
    with urllib.request.urlopen(req, timeout=3) as r:
        print(path, r.status)
PY" HOST_HEADER="$HOST_HEADER"

echo "PASS: probes ok"

