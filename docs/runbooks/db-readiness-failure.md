## DB readiness failure runbook

### Symptoms
- `/ready` returns `503` with `detail="Database unavailable"`
- `casino_bot_db_ready_state` is `0`
- Startup loops / migrations failing in CI or Docker

### Immediate checks
1. **Validate env**:
   - `python scripts/validate_env_contract.py --env-file .env` (or `.env.example` in CI)
2. **Wait for DB**:
   - `python scripts/wait_for_db.py --timeout-seconds 30`
3. **Connectivity**:
   - Host/port reachable from where the app runs (host vs Compose network)
   - Credentials match Postgres instance

### Common causes
- Wrong host in `DATABASE_URL` (e.g. `postgres` used outside Compose)
- Postgres not started / not healthy yet
- Migrations running before DB is ready (fixed in CI/Docker via `wait_for_db`)

### Recovery
- Start/repair Postgres, re-run:
  - `python scripts/wait_for_db.py --timeout-seconds 30`
  - `alembic upgrade head`

