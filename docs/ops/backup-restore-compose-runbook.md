## Backup/restore rehearsal (Docker Compose Postgres)

Scope: production-like rehearsal with **real** `pg_dump`/`pg_restore` against the Compose Postgres volume.

### Invariant
We can restore a backup into a **clean** database and the app becomes ready again.

### Artifacts
- Backups are stored under `./backups/` (gitignored).

### Preconditions
- Docker is installed and running.
- You have an env file (default: `.env.prod.example`) with:
  - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
  - `DATABASE_URL` points to the compose postgres host (`postgres`)
  - production app env required by `validate_env_contract`

### Commands (one-by-one)

1) Create backup:

```bash
ENV_FILE=.env.prod.example COMPOSE_FILE=docker-compose.prod.yml ./scripts/ops/pg_dump_compose.sh
```

2) Restore into a clean DB (destroys volume):

```bash
BACKUP_PATH=./backups/<file>.dump ENV_FILE=.env.prod.example COMPOSE_FILE=docker-compose.prod.yml ./scripts/ops/pg_restore_compose.sh
```

3) Verify app readiness/smoke:

```bash
HOST_HEADER=api.example.com ENV_FILE=.env.prod.example COMPOSE_FILE=docker-compose.prod.yml ./scripts/ops/pg_verify_compose.sh
```

### PASS/FAIL
PASS if:
- restore succeeds without errors
- `/health` 200, `/ready` 200, `/metrics` 200 from inside the api container

### Notes
- This does not cover WAL/PITR/snapshots. That is a later stage after this rehearsal is green.

