## External staging validation report — 2026-05-07

### Stack

- Compose: `docker-compose.staging.yml`
- TLS: self-signed (nginx termination)
- `/metrics`: protected by nginx basic auth

### E2E probe results

- `GET https://<domain>/health` → 200
- `GET https://<domain>/ready` → 200
- `GET https://<domain>/metrics` (no auth) → 401
- `GET https://<domain>/metrics` (basic auth) → 200

### Soak (sample)

Harness:

```bash
SOAK_BASE_URL=https://<domain> \
SOAK_HOST_HEADER=<domain> \
SOAK_INSECURE_TLS=true \
SOAK_METRICS_BASIC_AUTH='metrics:***' \
python scripts/soak/soak_http.py --duration-seconds 600 --interval-seconds 1
```

Sample result (30s):
- 5xx rate: 0.0000
- ready fail rate: 0.0000
- latency p95/p99: single-digit ms range (local test)
- db_ready_state min: 1

