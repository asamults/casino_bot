## HTTP 5xx spike runbook

### Reproduce (GameDay)
- `scripts/drill/drill_5xx_spike.sh`

### Symptoms
- Alert `CasinoBotHTTP5xxSpike` firing
  (`5xx rate > 1% over 10m sustained`)
- `casino_bot_http_requests_total{status=~"5.."}` increasing in Grafana
- Possible end-user impact (admin UI, billing webhooks)

### Immediate checks
1. **Confirm scope**:
   - Grafana dashboard `casino_bot_baseline`: which routes are emitting 5xx?
     Look at `casino_bot_http_request_duration_seconds` per `path_template`.
   - Single endpoint vs. fleet-wide?
2. **DB readiness**:
   - `casino_bot_db_ready_state` — if 0, this is a DB problem; jump to
     `db-readiness-failure.md`.
3. **Recent deploys**:
   - `git log --oneline -n 10` for recent `main` activity.
   - Active rollout / migration in progress?
4. **Logs**:
   - Application logs around the spike start time.
     Search for unhandled exceptions / `Internal server error`.
5. **Rate-limit / dependency saturation**:
   - Stripe/Paddle status pages if billing routes are involved.
   - DB connection pool saturation.

### Common causes
- A bad migration or schema mismatch after deploy.
- A downstream dependency (Stripe/Paddle/DB) returning errors.
- An unhandled code path in a recently merged feature.
- Misconfigured env (e.g. missing `STRIPE_WEBHOOK_SECRET` causing 500 on
  webhook validation).

### Recovery
1. **Roll back if release-correlated**:
   - See `docs/runbooks/rollback-procedure.md`.
2. **Stop the bleeding**:
   - For a single broken endpoint, consider feature-flagging it off.
   - For a flaky dependency, throttle or short-circuit at the edge.
3. **Verify recovery**:
   - Watch the alert for clear (`5xx_rate < 1%` for 10m).
   - Run `scripts/drill/smoke.sh` or `make drill-smoke` for a baseline.

### Post-incident
- Open an incident report from `docs/runbooks/incident-template.md`.
- Capture Grafana screenshots covering the spike window.
- File a ticket for the root cause if not already addressed by the
  rollback.
