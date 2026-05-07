## External staging checklist (executable)

### Setup
- [ ] `.env.staging` created (based on `.env.prod.example`)
- [ ] `ALLOWED_HOSTS` contains staging domain
- [ ] TLS cert present (self-signed or LE)
- [ ] `/metrics` auth file created: `ops/external-staging/nginx/.htpasswd`

### Bring up
- [ ] `docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build`
- [ ] `docker compose --env-file .env.staging -f docker-compose.staging.yml ps` shows `api` + `postgres` healthy

### Probes (PASS/FAIL)
- [ ] `curl -k https://<domain>/health` → **200**
- [ ] `curl -k https://<domain>/ready` → **200**
- [ ] `curl -k https://<domain>/metrics` → **401**
- [ ] `curl -k -u metrics:*** https://<domain>/metrics` → **200**

### Host hardening (PASS/FAIL)
- [ ] wrong Host returns 400:

```bash
curl -k https://127.0.0.1/health -H "Host: evil.example.com" -v
```

### CORS (PASS/FAIL)
- [ ] preflight from allowed origin returns correct allow-* headers

### Soak (PASS/FAIL)
- [ ] 10m soak via HTTPS:

```bash
SOAK_BASE_URL=https://<domain> \
SOAK_HOST_HEADER=<domain> \
SOAK_INSECURE_TLS=true \
SOAK_METRICS_BASIC_AUTH='metrics:***' \
python scripts/soak/soak_http.py --duration-seconds 600 --interval-seconds 1
```

PASS: `PASS: soak criteria met` and summary within SLO thresholds.

