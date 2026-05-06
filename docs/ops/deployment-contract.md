## Production deploy contract (baseline)

### Process contract (startup)

Required startup sequence:
- **wait_for_db**: `python scripts/wait_for_db.py --timeout-seconds 30`
- **migrations**: `alembic upgrade head`
- **app**: `uvicorn casino_bot.main:app --host 0.0.0.0 --port 8000`

### Probes

- **Liveness**: `GET /health` → `200 {"status":"ok"}`
- **Readiness**: `GET /ready`
  - `200 {"status":"ready"}` when DB reachable
  - `503` when DB unavailable; also sets `casino_bot_db_ready_state 0`
- **Metrics**: `GET /metrics` → Prometheus text format

### Migrations & rollback

- **Default policy**: forward-only migrations (upgrade to head).
- **Downgrade**: only when explicitly required; treat as a higher-risk operation.
  - Snapshot critical tables first.
  - Run a downgrade in a controlled environment before production.

### Environment / configuration

Production must set at least:
- `ENVIRONMENT=production`
- `DATABASE_URL`
- `SECRET_KEY`, `JWT_SIGNING_KEY`, `REFRESH_TOKEN_PEPPER` (>=32 chars, non-default)
- `USER_API_INTERNAL_TOKEN` (non-default)
- `CORS_ALLOW_ORIGINS` (explicit JSON list)
- `ALLOWED_HOSTS` (no localhost/loopback)
- `BILLING_ALLOWED_RETURN_HOSTS` (no localhost/loopback)

Production must **not** enable drill flags:
- `DRILL_FORCE_DB_NOT_READY`, `DRILL_FORCE_500_ON_PATH`, `DRILL_SUPERADMIN_TOKEN`

### `/metrics` access policy

`/metrics` is intentionally unauthenticated in-app. Deploy it **only**:
- inside a **private network** (Prometheus scrapes over internal DNS), or
- behind a reverse proxy that enforces auth/IP allowlist.

See: `docs/ops/metrics-access.md`.

