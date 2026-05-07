## Production rollback plan

### When to rollback
- **Availability**: `/ready` failing persistently (e.g. >10m) after a deploy
- **Error spike**: sustained 5xx rate above SLO and not quickly mitigated
- **Billing pipeline**: dead-letter growth indicating systemic breakage
- **Security**: suspected secret leak / auth bypass / policy regression

### What to rollback
- **Primary**: application code (container image/tag or git SHA)
- **Secondary** (only if required): configuration changes (env/proxy rules)
- **DB schema**:
  - Default: **do not downgrade**. Prefer forward fixes.
  - Downgrade only with explicit approval and pre-tested downgrade path.

### Evidence retention
- Do not delete `failed`/`dead_letter` webhook events via normal cleanup.
- Preserve logs and audit trails for incident analysis.

### Rollback steps (code)
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

