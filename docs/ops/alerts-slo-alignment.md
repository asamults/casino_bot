## Alerts ↔ SLO alignment audit (M6W1)

This document checks every Prometheus alert defined in
`monitoring/alert_rules.yml` against the SLOs in `docs/ops/slo.md`,
with a fix for one stale runbook reference and an explicit decision
about latency.

### Source of truth

- SLOs: `docs/ops/slo.md`
- Alerts: `monitoring/alert_rules.yml` (group `casino_bot_baseline`)

### Per-alert audit

| Alert                            | SLO target                         | Alert expr / window                  | Runbook                          | Aligned?                                               |
| -------------------------------- | ---------------------------------- | ------------------------------------ | -------------------------------- | ------------------------------------------------------ |
| `CasinoBotReadyDown`             | DB ready state must stay 1; any sustained 0 is a page | `casino_bot_db_ready_state == 0` for 2m            | `docs/runbooks/db-readiness-failure.md` | YES                                                    |
| `CasinoBotHTTP5xxSpike`          | HTTP 5xx rate `< 1%` over 10m      | `5xx ratio over [5m] > 0.01` for 10m | **fixed in M6W1** → `docs/runbooks/http-5xx-spike.md` | YES (alert is mildly stricter; see notes)              |
| `CasinoBotDeadLetterGrowth`      | Dead-letter total does not increase during normal soak | `increase(... [15m]) > 0` for 15m  | `docs/runbooks/webhook-dead-letter.md`  | YES                                                    |

### Issue found and fixed

`CasinoBotHTTP5xxSpike` previously pointed at
`docs/runbooks/ci-gates-failure.md`, which is a CI-pipeline runbook, not
an HTTP-5xx incident response playbook. Operators paged at 03:00 would
get the wrong document. **Fixed in M6W1** by:

1. Adding `docs/runbooks/http-5xx-spike.md` with concrete triage steps,
   reproduction via `scripts/drill/drill_5xx_spike.sh`, and a recovery
   path.
2. Pointing the `runbook` annotation in `alert_rules.yml` at the new
   runbook.

This is the kind of stale-link rot that audits like this are designed
to catch.

### Window analysis: 5xx alert vs. SLO

- **SLO statement**: `5xx_rate < 1% over a 10m window`.
- **Alert expression**: 5-minute rate of 5xx > 1% **sustained for 10
  minutes**.

These are not mathematically identical. A flat 10-minute average is
slightly more forgiving than "10 consecutive minutes of >1% short-term
rate". The current form is preferred because:

- A single 30-second 5xx burst that averages out under 1% over 10
  minutes wouldn't fire either way.
- A persistent 5xx wave (the case we want to be paged for) saturates
  the 5-minute rate immediately and trips the 10-minute `for` clause.
- Using a 10-minute rate as both the expr window and the `for` would
  lengthen detection to roughly 20 minutes after onset.

This is documented here rather than re-stated in `slo.md` to avoid two
sources of truth diverging.

### Latency: deliberate alert gap

`slo.md` lists **HTTP p95 < 500ms** as an SLO. There is no Prometheus
alert for it.

Decision: keep latency as a **soak / dashboard** signal, not a paging
alert.

Rationale:

- Latency alerts at this maturity stage tend to flap during deploys,
  rolling restarts, and any migration touchwork. The cost of training
  operators to ignore "noisy" latency pages is higher than the value of
  the alert at our current scale.
- The soak harness (`scripts/soak/soak_http.py`) already measures p95
  and is part of the M3-style soak validation. The `m4` soak validation
  report logs p95.
- Grafana dashboard `casino_bot_baseline` exposes
  `casino_bot_http_request_duration_seconds` for trend review.

If/when the deployment cadence stabilizes and the platform supports
SLO-burn-rate alerting (multi-window, multi-burn-rate per Google's SRE
workbook), latency moves into a real alert at that point. Tracked as a
"future work" item in the team's ops backlog, not in M6W1.

### Verdict

PASS at M6W1. Three alerts, three SLOs, three runbooks. One stale
runbook reference fixed. One deliberate gap (latency) explicitly
documented.
