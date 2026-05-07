## Metrics access policy

### Default posture

`GET /metrics` is **not authenticated by the app**. Treat it as
operational telemetry and expose it only:

- inside a private network/VPC, or
- through a reverse proxy with IP allowlist and/or auth.

The casino_bot codebase ships *turnkey* configs for the proxy path —
this is the recommended approach for any deployment touching the open
internet.

### Golden path (M6W2)

1. **Generate a hashed credentials file** with the bundled script:

   ```bash
   USERNAME=metrics ./scripts/ops/htpasswd_gen.sh
   # prompts for password (no echo); writes ./.htpasswd (mode 0600).
   # Encoder: htpasswd -B (bcrypt) if available; otherwise openssl apr1.
   ```

   The output file is gitignored by `*.htpasswd` in `.gitignore`. Never
   commit it. The script refuses passwords shorter than 12 chars.

2. **Mount the file into the proxy**. Both shipped configs are wired
   for this:

   - `ops/reverse-proxy/nginx.conf.example` (generic)
   - `ops/external-staging/nginx/nginx.conf` (staging HTTPS)

   Either one looks for `/etc/nginx/.htpasswd` inside the container;
   the bundled compose file in `ops/reverse-proxy/docker-compose.proxy.yml`
   bind-mounts `./.htpasswd` to that path.

3. **Verify** with the smoke script:

   ```bash
   BASE_URL=https://<host> \
   METRICS_BASIC_AUTH=metrics:<password> \
   INSECURE_TLS=true \
     ./scripts/ops/verify_proxy_policies.sh
   ```

   Expected: `/metrics` without auth → 401/403; with valid basic auth
   → 200.

4. **Production preflight** (`scripts/ops/production_preflight.sh`)
   already enforces the `/metrics` policy end-to-end as part of the
   cutover dry-run. It fails closed unless either:

   - `METRICS_BASIC_AUTH=user:pass` is provided (and the proxy
     correctly returns 401/403 then 200), **or**
   - `METRICS_PUBLIC=true` is explicitly opted in (e.g. metrics behind
     a private network where exposing them is acceptable).

### Alternative: IP allowlist instead of basic auth

If your network already has a sharply-scoped private path to the api
host, an IP allowlist may be sufficient and avoids credential
distribution:

```nginx
location = /metrics {
  allow 10.0.0.0/8;
  deny all;
  proxy_pass http://api:8000/metrics;
}
```

Combine with basic auth for defence-in-depth in higher-stakes
deployments.

### Why exact-match `location = /metrics`

Both shipped configs use `location = /metrics` (exact match) rather
than a prefix. Reasoning: the FastAPI app exposes only `/metrics`
itself; if a future feature ever adds `/metrics/foo`, an exact-match
guarantees the new endpoint won't accidentally inherit a permissive
policy. New paths trip the default `location /` block and the operator
must consciously decide on access semantics.

### See also

- `docs/ops/admin-access-policy.md` — the same proxy hardens admin
  routes via a separate IP allowlist.
- `docs/ops/secrets-hygiene.md` — `*.htpasswd` is on the forbidden
  paths list; CI fails if one ends up in the repo.
- `scripts/ops/htpasswd_gen.sh` — generator (turnkey).
- `scripts/ops/verify_proxy_policies.sh` — smoke (turnkey).
