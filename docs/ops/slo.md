## SLOs (staging baseline)

These SLOs are **staging expectations** used for soak validation and alert tuning. They are intentionally pragmatic (not strict production commitments).

### Availability / readiness

- **Readiness success rate** (`/ready`): **>= 99.9%** over a 60m window.
- **DB readiness state** (`casino_bot_db_ready_state`): must stay **1** (any sustained 0 is a page).

### Errors

- **HTTP 5xx rate**: **< 1%** over a 10m window (page alert may be higher to avoid flapping during deploys; tune with soak evidence).

### Latency

- **HTTP p95** (key routes like `/health`, `/ready`): **< 500ms** in staging.

### Billing pipeline

- **Dead-letter growth** (`casino_bot_webhook_dead_letter_total`): **0** increases during normal staging soak (ticket if non-zero; investigate via runbook).

### Acceptance criteria (soak run PASS)

A soak run is **PASS** if:
- `/ready` failures are below 0.1% for the run duration
- 5xx rate is below 1% for the run duration
- p95 latency is below 500ms
- `casino_bot_db_ready_state` never dips below 1
- dead-letter total does not increase (unless intentionally exercised)

