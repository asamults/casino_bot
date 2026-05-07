## Staging rehearsal checklist (M4W1)

This is an executable, production-like rehearsal using `docker-compose.prod.yml`.

### Preconditions

- `main` clean, CI green
- Docker is running
- Use `--env-file .env.prod` with real secrets (example template: `.env.prod.example`)

### 1) Bring up production-like stack (PASS/FAIL)

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

**PASS**:
- `casino_bot-postgres` is `healthy`
- `casino_bot-api` is `healthy`

### 2) Probes from inside the container (PASS/FAIL)

Because production enables host hardening (`TrustedHostMiddleware`), probes must use an allowed `Host`.

```bash
docker exec casino_bot-api bash -lc "python - <<'PY'
import urllib.request
host='api.example.com'  # must be in ALLOWED_HOSTS
for p in ('/health','/ready','/metrics'):
    req=urllib.request.Request('http://127.0.0.1:8000'+p, headers={'Host':host})
    with urllib.request.urlopen(req, timeout=3) as r:
        print(p, r.status)
PY"
```

**PASS**:
- `/health 200`
- `/ready 200`
- `/metrics 200`

### 3) Migration visibility and idempotent restart (PASS/FAIL)

```bash
docker logs casino_bot-api --tail=200
docker compose --env-file .env.prod -f docker-compose.prod.yml restart api
sleep 5
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

**PASS**:
- logs show DB wait succeeded and Alembic upgrade ran
- restart returns the API back to `healthy` without errors

### 4) `/metrics` access policy verification (PASS/FAIL)

**PASS** (choose one model):
- private network only: `/metrics` is reachable only from inside the docker network, or
- reverse proxy enforces basic auth / IP allowlist for `/metrics`.

Reference config: `docs/ops/metrics-access.md`.

### 5) Tear down

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml down
```

