## External staging (domain + TLS + reverse proxy)

This is an end-to-end staging stack that terminates TLS at a reverse proxy and keeps the API container private.

### Prereqs

- A staging domain (example): `api.example.com`
- `ALLOWED_HOSTS` includes the staging domain
- Docker running on a host that can bind ports **80/443**
- `htpasswd` (apache2-utils) to generate basic auth file for `/metrics`

### TLS options

#### Option A: self-signed (quick)

```bash
./ops/external-staging/generate_self_signed_tls.sh api.example.com
```

Use `curl -k` and `SOAK_INSECURE_TLS=true` for verification.

#### Option B: Let’s Encrypt (real DNS + public reachability)

Recommended: terminate TLS with a dedicated ACME-aware proxy (Caddy/Traefik) or run certbot on the host.
This repo ships self-signed by default; LE wiring depends on your infrastructure.

### Bring up staging stack

1) Create `.env.staging` (start from `.env.prod.example`) and set:
- `STAGING_DOMAIN=api.example.com`
- `ALLOWED_HOSTS=api.example.com`
- `CORS_ALLOW_ORIGINS=[\"https://admin.example.com\"]` (your admin UI origin)

2) Create `/metrics` basic auth file:

```bash
htpasswd -c ops/external-staging/nginx/.htpasswd metrics
#
# Alternative without htpasswd (uses openssl):
# printf "metrics:%s\n" "$(openssl passwd -apr1 'yourpass')" > ops/external-staging/nginx/.htpasswd
```

3) Start stack:

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build
docker compose --env-file .env.staging -f docker-compose.staging.yml ps
```

### End-to-end checks (expected output)

```bash
curl -k https://api.example.com/health
curl -k https://api.example.com/ready
curl -k https://api.example.com/metrics
curl -k -u metrics:YOURPASS https://api.example.com/metrics | head
```

Expected:
- `/health` → 200
- `/ready` → 200
- `/metrics` without auth → 401
- `/metrics` with auth → 200

### TrustedHost validation

```bash
curl -k https://127.0.0.1/health -H "Host: evil.example.com" -v
```

Expected:
- `400 Bad Request` from `TrustedHostMiddleware`

### CORS validation (preflight)

```bash
curl -k -X OPTIONS https://api.example.com/api/v1/admin/ping \
  -H "Origin: https://admin.example.com" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: Authorization,Content-Type"
```

Expected:
- `Access-Control-Allow-Origin: https://admin.example.com`
- allow-headers includes `Authorization, Content-Type`

### Soak via public HTTPS URL

Run from your workstation (or a runner that can reach the domain):

```bash
SOAK_BASE_URL=https://api.example.com \
SOAK_HOST_HEADER=api.example.com \
SOAK_INSECURE_TLS=true \
SOAK_METRICS_BASIC_AUTH='metrics:YOURPASS' \
python scripts/soak/soak_http.py --duration-seconds 600 --interval-seconds 1
```

