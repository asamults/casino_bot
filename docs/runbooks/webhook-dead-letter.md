## Webhook dead-letter runbook

### Symptoms
- Increasing `casino_bot_webhook_dead_letter_total`
- Admin shows `dead_letter=true` events
- Missing entitlement updates / billing sync

### Immediate checks
- **Check provider health**: Stripe/Paddle status page, API availability.
- **Check app readiness**: `GET /ready` must be `200`.
- **Check backlog**:
  - `GET /api/v1/admin/billing/events?status=failed`
  - `GET /api/v1/admin/billing/events?dead_letter=true`

### Triage steps
1. **Identify error code** (metrics label `error_code` and `last_error_code` on events):
   - `mapping_failed`: user/customer mapping missing
   - `processing_error`: unexpected runtime failure
2. **For mapping_failed**:
   - Link customer/subscription IDs to user
   - `POST /api/v1/admin/billing/events/{id}/replay` (or replay-failed batch)
3. **For processing_error**:
   - Inspect logs for `billing_webhook` and `request_id`
   - Fix root cause; then replay

### Recovery
- Replay failed (non-dead-letter) events: `POST /api/v1/admin/billing/events/replay-failed`
- Undelete dead-letter after fix (superadmin): `POST /api/v1/admin/billing/events/{id}/undelete-dead-letter`

### Notes
- Normal retention cleanup does **not** delete `failed` / `dead_letter` (evidence trail).

