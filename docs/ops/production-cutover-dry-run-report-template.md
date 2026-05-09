## Production cutover dry-run report (TEMPLATE)

Date: YYYY-MM-DD  
Owner: `<name>`  
Target SHA/tag: `<sha or vX.Y.Z>`  
Production API hostname: `<api.example.com>`  

### Repo gates (typically PASS from CI)
- Target SHA CI green (Security Gates + smoke workflows): PASS/FAIL
- `HEALTHCHECK_HOST` present in compose env alongside `ALLOWED_HOSTS`: PASS/FAIL

### Preflight (host)
- Env contract validation (`ENVIRONMENT=production` + `--env-file` host path): PASS/FAIL
- Secrets inventory reviewed: PASS/FAIL
- DB backup plan confirmed / tested restore drill: PASS/FAIL

### DNS
- TTL reduced: PASS/FAIL (value)
- Rollback DNS target identified: PASS/FAIL

### TLS / reverse proxy
- TLS configured: PASS/FAIL (Let’s Encrypt / existing); `curl -v` validates SNI / hostname chain
- `/metrics` policy enforced: PASS/FAIL (401/403 without auth; 200 with auth OR private scrape)
- TrustedHost / Host header validated: PASS/FAIL

### Smoke (`scripts/ops/production_preflight.sh`)
- `/health`: PASS/FAIL
- `/ready`: PASS/FAIL
- `/metrics` unauthenticated forbidden (unless `METRICS_PUBLIC=true` explicitly): PASS/FAIL
- Legacy deprecation headers (`LEGACY_ENDPOINTS`): PASS/FAIL

### Observability (`monitoring/docker-compose.observability.yml`)
- Prometheus scrapes `api`: PASS/FAIL
- Grafana dashboards + alert rules reachable: PASS/FAIL

### Backups
- `pg_backup_encrypt` cron documented (schedule + log path + artifact dir): PASS/FAIL
- Off-host copy cron (optional): PASS/FAIL

### Restart resilience
- `docker compose restart` / host reboot survives without manual migrations: PASS/FAIL

### Rollback readiness
- `docs/ops/production-rollback-plan.md` exercised or walkthrough-complete: PASS/FAIL

### Notes / issues found (include M7W2 perimeter gaps if any)
- `<bullets>`

### Post-cutover (after traffic; optional block)
Cutover timestamps, digest, rollback window, known risks — see filled example  
`production-cutover-dry-run-report-2026-05-07.md`.

### Decision
Ready for production cutover: YES/NO  
