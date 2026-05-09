## Production cutover dry-run report (M7W1)

Date: **2026-05-07**  
Owner: **`<operator>`**  
Target SHA/tag: **`<release git SHA / image digest>`**  
Production API hostname: **`(e.g. api.example.com)`**

**Repository / docs readiness:** **PASS** (this PR)

**Production host cutover status:** **`PENDING_OPERATOR`** — replace with **PASS** once all Host rows below are validated on the real VPS/domain.

---

### Repo / process readiness (CI + contracts)

| Item                                        | Status |
| ------------------------------------------- | ------ |
| Security Gates CI green on deploy SHA (confirm at cutover window)             | _____ |
| `docker-compose.prod.yml` requires `HEALTHCHECK_HOST` (compose contract)       | PASS   |
| `monitoring/docker-compose.observability.yml` + provisioning present | PASS   |
| Backup script path documented (`scripts/ops/pg_backup_encrypt.sh`) | PASS   |
| Cutover checklist + rollback plan updated   | PASS   |

---

### Preflight (host)

| Item                                                | PASS/FAIL |
| --------------------------------------------------- | --------- |
| `ENVIRONMENT=production` + `.env.prod` contract validation | _____ |
| Secrets only on VPS (never in git)                   | _____ |
| DB migration path (`alembic upgrade head` on boot) understood | _____ |

---

### DNS

| Item                    | PASS/FAIL | Notes |
| ----------------------- | --------- | ----- |
| TTL lowered pre-cutover | _____     | _____ |
| Rollback DNS target     | _____     | _____ |

---

### TLS / reverse proxy + SNI

| Item                                                              | PASS/FAIL |
| ----------------------------------------------------------------- | --------- |
| Browser shows valid HTTPS for prod hostname                       | _____     |
| `curl -v https://<host>/health` validates chain + hostname (SNI)   | _____     |
| TrustedHost rejects wrong `Host:` (HTTP 400)                      | _____     |
| `/metrics` not anonymously public (**401/403** or private scrape)| _____     |

---

### Smoke (HTTPS)

Recorded via `./scripts/ops/production_preflight.sh` where applicable:

| Endpoint / check              | PASS/FAIL |
| ----------------------------- | --------- |
| `/health`                     | _____     |
| `/ready`                      | _____     |
| `/metrics` without auth denied| _____     |
| `/metrics` with auth OK       | _____     |

**Happy path:** _(document one authenticated admin READ or safe write if in scope —
no new product features)._  
**Webhook provider (optional):** _(PASS / N/A — vendor + event type tested)._

---

### Observability

| Item                                                           | PASS/FAIL |
| -------------------------------------------------------------- | --------- |
| Prometheus scrapes `/metrics` on `casino_bot_default`          | _____     |
| Grafana reachable (recommended: SSH tunnel to `127.0.0.1:3000`)| _____     |
| `monitoring/alert_rules.yml` loaded (check Prometheus UI/rules)| _____     |

---

### Backups & retention

| Item                                             | PASS/FAIL | Notes _(paths redact secrets)_ |
| ------------------------------------------------ | --------- | ------------------------------- |
| Daily `pg_backup_encrypt` cron installed         | _____     | e.g. `/var/log/casino_bot/pg_backup.log` |
| Artifact directory writable                      | _____     | e.g. `/opt/casino_bot/backups/` |
| Off-host copy cron (optional)                    | _____     | `BACKUP_DEST=…`, tool `rsync/scp` |

---

### Restart resilience

| Scenario                         | PASS/FAIL | Notes |
| -------------------------------- | --------- | ----- |
| `docker compose restart api`     | _____     | _____ |
| VPS reboot (`reboot`)            | _____     | _____ |

---

### Rollback rehearsal

| Item                                                  | PASS/FAIL |
| ----------------------------------------------------- | --------- |
| `docs/ops/production-rollback-plan.md` steps understood | _____   |
| Tagged “last known good” SHA / image digest available | _____   |

---

### M7W2 perimeter gap (explicit)

Record anything intentionally **not** done in M7W1:

| Gap (e.g. admin geo allowlist, mTLS, WAF tuning) | Follow-up milestone |
| ------------------------------------------------ | ------------------- |
| _…_                                               | **M7W2** |

---

### Post-cutover (fill only after prod traffic begins)

Cutover UTC time (**start → stable /ready**): **_____**

Running image/registry digest(s): **_____**

Rollback window / owner: **_____**

Known risks / watch items: **_____**

**Post-traffic alert tuning:** see `docs/ops/alerts-slo-alignment.md` → *M7W1 appendix*.
