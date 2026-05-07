## SLO validation report (staging soak) — 2026-05-07

### Scope

- Environment: `docker-compose.prod.yml` (production-like)
- Soak harness: `scripts/soak/soak_http.py` (executed inside `casino_bot-api`)
- Host hardening: `TrustedHostMiddleware` enabled; probes use `Host: api.example.com`

### Run parameters

- Duration: 20s (sample)
- Interval: 0.5s
- Paths: `/health`, `/ready`, `/metrics`

### Results (PASS/FAIL)

**PASS** (sample run; adjust thresholds after longer soak).

### Key numbers

- Readiness fail rate: 0.0000
- 5xx rate: 0.0000
- Latency: p95=7.1ms p99=8.1ms
- `casino_bot_db_ready_state`: min=1
- Dead-letter delta: n/a (no dead-letter metric observed in this run)

### Alerts observed

- None during the sample run.

### Notes / follow-ups

- This report is generated from a short sample run to validate the harness and contract.
- For the full soak (N hours), capture:
  - start/end timestamps
  - Prometheus graphs (5xx rate, p95, db_ready_state, dead_letter)
  - any alert firings with runbook links and outcomes

