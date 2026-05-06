## GameDay checklist (local / docker-compose)

### Pre-flight
- [ ] `make ci-check` is green on current branch
- [ ] `docker compose up -d --build`
- [ ] Baseline smoke: `scripts/drill/smoke.sh`
- [ ] Monitoring (optional): `docker compose --profile monitoring up -d`
- [ ] If Postgres is started standalone (without `api`), host scripts need `DATABASE_URL`, e.g. `DATABASE_URL=postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db python scripts/wait_for_db.py`

### Drill scenarios
- [ ] **DB down / readiness**: `scripts/drill/drill_db_down.sh`
  - Runbook: `docs/runbooks/db-readiness-failure.md`
- [ ] **Webhook dead-letter**: `DRILL_SUPERADMIN_TOKEN=dev-drill-superadmin-token scripts/drill/drill_webhook_dead_letter.sh`
  - Runbook: `docs/runbooks/webhook-dead-letter.md`
- [ ] **5xx spike**: `scripts/drill/drill_5xx_spike.sh`
  - Postmortem template: `docs/runbooks/incident-template.md`

### Restore / rollback discipline
- [ ] Pick restore tag (example): `git tag --list | tail`
- [ ] Restore drill: `scripts/drill/restore_from_tag.sh <tag>`
  - Runbook: `docs/runbooks/rollback-procedure.md`

### Evidence to capture
- [ ] Drill output (PASS/FAIL) with `request_id`
- [ ] `docker compose ps` + `docker compose logs --no-color --tail=200 api`
- [ ] `/metrics` snapshot (or Prometheus/Grafana screenshots if enabled)
- [ ] Link to filled postmortem: `docs/runbooks/incident-template.md`

