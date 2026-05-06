## Rollback procedure

### Goal
Return service to last known good state while preserving evidence (audit logs, webhook dead-letter).

### Restore drill (GameDay)
- `scripts/drill/restore_from_tag.sh <tag>`
- Smoke validation: `scripts/drill/smoke.sh`

### Steps
1. **Pick target SHA/tag** (last green deploy).
2. **Deploy code rollback** (container image/tag or git SHA).
3. **DB migrations**
   - Prefer **forward-only** when possible.
   - If downgrade is required, read the relevant Alembic downgrade notes and snapshot critical tables first.
4. **Validate**
   - `/health` and `/ready`
   - `/metrics` (error spike / readiness gauge)
   - Billing webhook pipeline status and dead-letter counts

### Evidence retention
- Do not delete `failed`/`dead_letter` webhook events via regular cleanup.

