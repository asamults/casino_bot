## Production rollback plan

### When to rollback
- **Availability**: `/ready` failing persistently (e.g. >10m) after a deploy
- **Error spike**: sustained 5xx rate above SLO and not quickly mitigated
- **Billing pipeline**: dead-letter growth indicating systemic breakage
- **Security**: suspected secret leak / auth bypass / policy regression

### What to rollback
- **Primary**: application **container image/tag** or **compose build** pinned to last known-good **git SHA**
- **Secondary** (only if required): `.env.prod` entries or reverse-proxy policy
- **DNS**: point hostname back at previous target if the incident is infra-specific
- **DB schema**:
  - Default: **do not downgrade**. Prefer forward fixes.
  - Downgrade only with explicit approval and pre-tested downgrade path.

### Compose / VPS rollback (recommended path)

Assume repo checkout at `/opt/casino_bot` and compose project `casino_bot`.

1. **Stop ingress** (optional but reduces user-visible errors during swap):
   - pause proxy upstream, OR return maintenance at proxy layer.

2. **Checkout / pin image**:
   - `git fetch && git checkout <last-known-good-sha>`  
     **or** set `image:` / build cache policy if you deploy from a registry digest.

3. **Redeploy app stack**:

   ```bash
   docker compose --env-file .env.prod -f docker-compose.prod.yml down
   docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
   ```

   Do **not** remove the `pgdata` volume unless you intentionally restore DB from backup.

4. **Restart monitoring** only if Prometheus rules or scrape config broke:

   ```bash
   docker compose -f monitoring/docker-compose.observability.yml restart
   ```

5. **Verify** (HTTPS + Host header):

   ```bash
   BASE_URL=https://<prod-host> HOST_HEADER=<prod-host> \
     METRICS_BASIC_AUTH=metrics:*** \
     ./scripts/ops/production_preflight.sh
   ```

### Evidence retention
- Do not delete `failed`/`dead_letter` webhook events via normal cleanup.
- Preserve logs and audit trails for incident analysis.

### Rollback steps (abbreviated, any substrate)
1. Select rollback target SHA/tag (last known good).
2. Deploy that version.
3. Validate:
   - `/health` and `/ready`
   - `/metrics` key series present
   - basic billing/admin sanity (optional)

### Rollback steps (DB)
If DB downgrade is truly required:
1. Snapshot critical tables (at minimum `billing_webhook_events`, `subscriptions`, audit logs).
2. Run downgrade in a controlled environment first.
3. Execute downgrade in production with maintenance window and monitoring.

### Verify recovery
- `/ready` stays 200
- 5xx rate returns to baseline
- dead-letter stops growing (or returns to normal expected rate)
