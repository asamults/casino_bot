## Production cutover readiness checklist (M7W1 — single VPS baseline)

Goal: confirm we can run **one real production host** (1× VPS) with
`docker-compose.prod.yml`, TLS at a reverse proxy, optional monitoring
sidecar, documented backup cron — **before** or **during** DNS cutover.

Secrets live only on the host (`.env.prod`, proxy creds, Grafana
password). Never commit them.

### Target topology (minimal)

- **VPS**: Ubuntu LTS (or equivalent) with Docker Engine + Compose v2.
- **App stack**: `postgres` + `api` from `docker-compose.prod.yml`  
  (project name `casino_bot` unless you override; default bridge network
  `casino_bot_default`).
- **TLS**: terminates at **nginx** or **Caddy** on the same host or a DMZ host;
  upstream to the Docker network (recommended: attach proxy containers to
  `casino_bot_default` like `docker-compose.staging.yml` / `docs/ops/external-staging.md`).
- **Monitoring** (recommended): Prometheus + Grafana via
  `monitoring/docker-compose.observability.yml` (joins `casino_bot_default`;
  Prometheus scrapes `api:8000` per `monitoring/prometheus.yml`).

### Preflight (must pass before touching production DNS/TLS)

- [ ] `git status` clean; intended release **SHA/tag** recorded
- [ ] CI green on that SHA (Security Gates + smoke workflows)
- [ ] `ENVIRONMENT=production` env contract validated (host-only file):

  ```bash
  ENVIRONMENT=production python scripts/validate_env_contract.py --env-file /path/to/.env.prod
  ```

  Adjust `DATABASE_URL` and other vars in the subprocess environment if your
  validator invocation requires overrides (mirror CI prod gate).

- [ ] `.env.prod` on the VPS includes **`HEALTHCHECK_HOST`** identical to the
      primary hostname in **`ALLOWED_HOSTS`** (`docker-compose.prod.yml` requires
      it so `/ready` healthchecks survive TrustedHost).
- [ ] On-call owner and maintenance window agreed
- [ ] `docs/ops/production-rollback-plan.md` read and rollback target tagged

### DNS

- [ ] Production API hostname chosen (example: `api.example.com`)
- [ ] TTL lowered ahead of cutover (e.g. 60–300s)
- [ ] A/AAAA or CNAME → VPS public IP/target
- [ ] Rollback: previous target or TTL extension documented

### TLS / reverse proxy

- [ ] HTTPS works in browser **and** matches cert hostname
- [ ] **`curl -v`** from outside confirms certificate chain & SNI (replace host):

  ```bash
  curl -v --resolve api.example.com:443:<PUBLIC_IP> https://api.example.com/health
  ```

- [ ] **`ALLOWED_HOSTS`** equals production API hostname (comma-list only if deliberate)
- [ ] **`/metrics`**: enforced at proxy (**basic auth** or **private scrape** —
      see `docs/ops/metrics-access.md`). In-app `/metrics` is unauthenticated.

**M7W2 gap (explicit, if deferred):** full **admin surface** geo allowlist /
mTLS audit logging per `docs/ops/admin-access-policy.md`. If prod proxy only does
TLS + `/metrics` auth, record that gap in the cutover report.

### Env / secrets

- [ ] `docs/ops/secrets-inventory.md` reviewed
- [ ] Host has non-example values for at least:
      `SECRET_KEY`, `JWT_SIGNING_KEY`, `REFRESH_TOKEN_PEPPER`,
      `USER_API_INTERNAL_TOKEN`, DB password, webhook secrets if enabled
- [ ] Drill / test flags **absent** in prod (`docs/ops/deployment-contract.md`)

### DB migrations

- [ ] Cold start acceptable: compose runs `wait_for_db` → `alembic upgrade head` → uvicorn
- [ ] Forward-only rollback policy understood

### Compose bring-up order (operator)

Approximate golden path on the VPS (paths illustrative):

```bash
cd /opt/casino_bot   # checkout at release SHA
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
```

If using the **monitoring sidecar**:

```bash
export GRAFANA_ADMIN_PASSWORD='***'   # host secret
docker compose -f monitoring/docker-compose.observability.yml up -d
```

Prometheus evaluates `monitoring/alert_rules.yml` (see §Observability).

### Smoke (HTTPS, via proxy + real Host)

Load **production secrets into the shell** from the host-managed env file **without echoing**:

```bash
set -a
# shellcheck disable=SC1091
source /secure/casino_bot.env.prod   # operator path; contents must satisfy Settings()
set +a
BASE_URL=https://api.example.com \
HOST_HEADER=api.example.com \
METRICS_BASIC_AUTH=metrics:*** \
  ./scripts/ops/production_preflight.sh
```

Minimal manual checks:

- [ ] `GET /health` → 200
- [ ] `GET /ready` → 200
- [ ] **Happy path**: one authenticated admin call succeeds if admin is in scope
      (same pattern as README `ADMIN_EMAIL` login + one list endpoint — no new features).

### Restart resilience

- [ ] After `docker compose ... restart api` **or** `reboot`, stack returns to
      healthy without manual Alembic (compose startup runs migrations).

### Observability

- [ ] Prometheus scrapes `api:8000` on `casino_bot_default` (`/metrics`; may be blocked
      from outside if only internal scrape — that is acceptable if metrics are private)
- [ ] Grafana loads **casino_bot_baseline** dashboard (loopback `:3000` + SSH tunnel)
- [ ] Alert rules loaded (see `monitoring/alert_rules.yml` vs `docs/ops/slo.md`)

### Backups (cron-ready)

Artifacts: encrypted dump + `.sha256` + `.meta.json` under `backups/` (default), then
optional off-host copy per `docs/ops/offhost-backup-runbook.md`.

**Do not commit** recipient keys, identity files, or `BACKUP_DEST` credentials.

Example **daily** cron on the VPS (04:15 UTC):

```cron
15 4 * * * cd /opt/casino_bot && ENV_FILE=.env.prod COMPOSE_FILE=docker-compose.prod.yml \
  /usr/bin/flock -n /tmp/casino_bot_pg_backup.lock \
  ./scripts/ops/pg_backup_encrypt.sh >> /var/log/casino_bot/pg_backup.log 2>&1
```

Off-host mirror (hourly optional):

```cron
55 * * * * cd /opt/casino_bot && BACKUP_FILE=/opt/casino_bot/backups/$(ls -1t backups/*.dump.age | head -1) \
  BACKUP_DEST=/var/backups/casino_bot_mirror/ COPY_TOOL=rsync VERIFY=true \
  ./scripts/ops/offhost_copy.sh >> /var/log/casino_bot/offhost_copy.log 2>&1
```

Adjust paths (`ls` → explicit latest file naming in your wrapper if preferred).

Optional **systemd** timer instead of cron: wrap the same command in `ExecStart=`
and rely on journald (`After=docker.service`).

### Rolling dry-run evidence

- [ ] Complete `docs/ops/production-cutover-dry-run-report-YYYY-MM-DD.md` from
      `production-cutover-dry-run-report-template.md` → **PASS** or honest **FAIL**.

### Rollback readiness

- [ ] `docs/ops/production-rollback-plan.md` steps applicable to compose + image tag

### Evidence retention / billing hygiene

- [ ] Confirm dead-letter retention policy unchanged (`docs/runbooks/webhook-dead-letter.md`)
