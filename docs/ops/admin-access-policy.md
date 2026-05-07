## Admin surface access policy (M6W2)

Goal: keep the casino_bot **admin surface** unreachable from the open
internet *at the network layer*, on top of the JWT-based auth the app
already enforces. This is **defence-in-depth** — if a token leaks or
brute-force traffic finds the public IP, the proxy denies before the
app even sees it.

### Scope

The "admin surface" is every route under:

- `/admin/*`           (legacy; emits `Deprecation` + `Sunset` headers)
- `/api/v1/admin/*`    (canonical)

This includes login, refresh, logout, ping, users, audit-logs, billing
admin, and so on. All of them go through the same allowlist gate.

### Threat model (what this protects against)

- A leaked admin JWT being used from an arbitrary internet IP.
- Credential-stuffing / password-spray against `/admin/login` from
  random IPs.
- Internet-discovered admin endpoints being brute-forced or fingerprinted.

It does **not** protect against:
- A compromised allowlisted host (VPN endpoint owned, office laptop owned).
  → Compensating control: short-lived sessions + logout-all rotation
  (`docs/ops/emergency-auth-ops.md`).
- A leaked refresh token from a session that was issued legitimately.
  → Same compensating control as above.

### Where to enforce

At an **external reverse proxy** in front of the api container.
The repo ships two reference configs:

| File                                             | Use                                            |
| ------------------------------------------------ | ---------------------------------------------- |
| `ops/reverse-proxy/nginx.conf.example`           | Generic example (HTTP, port 8080)              |
| `ops/external-staging/nginx/nginx.conf`          | Real staging proxy (HTTPS, port 443)           |

The example config (M6W2) demonstrates all three policies — admin IP
allowlist, metrics basic auth, and open probes. Copy it as the basis
for new environments.

### Allowlist policy

Implemented in nginx via a `geo` block:

```nginx
geo $admin_allowed {
  default 0;
  10.0.0.0/8       1;   # corporate VPN
  192.0.2.0/24     1;   # office NAT
  198.51.100.42/32 1;   # bastion host
}

location /admin {
  if ($admin_allowed = 0) { return 403; }
  proxy_pass http://casino_bot_api;
}
location /api/v1/admin {
  if ($admin_allowed = 0) { return 403; }
  proxy_pass http://casino_bot_api;
}
```

Rules:

1. **Default-deny.** `default 0` is mandatory; the safe posture if an
   operator forgets to populate the allowlist is "nobody can reach
   admin".
2. **Smallest CIDR that does the job.** Avoid `0.0.0.0/0` "temporary"
   workarounds — they always become permanent.
3. **No `allow ... ; deny all;` in the location block** — that pattern
   evaluates per-request and is harder to reason about than a single
   `geo`-driven boolean.
4. **The app keeps its own auth.** Removing the allowlist must never
   open the admin surface; the app's JWT-based admin guard remains the
   primary control.

### Optional: basic auth on top

For environments that lack a stable VPN/office IP set (e.g. fully
remote ops team using rotating residential IPs), add HTTP basic auth in
front of the allowlist:

```nginx
location /admin {
  auth_basic "casino_bot admin";
  auth_basic_user_file /etc/nginx/.htpasswd-admin;
  proxy_pass http://casino_bot_api;
}
```

Generate the `.htpasswd-admin` file with `scripts/ops/htpasswd_gen.sh`
(prefers `htpasswd -B` bcrypt, falls back to `openssl passwd -apr1`).
This is **in addition to** allowlist where possible, not a replacement.

### Optional: mTLS

For the highest-stakes deployments (e.g. multi-customer prod), require a
client certificate at the proxy:

```nginx
ssl_client_certificate /etc/nginx/tls/admin-ca.crt;
ssl_verify_client on;

location /admin {
  proxy_pass http://casino_bot_api;
}
```

mTLS is operationally heavier (CA management, cert rotation, distribution)
and is **not** the M6W2 default. Document it as an option for
environments that already have a working internal CA.

### Verification

Use `scripts/ops/verify_proxy_policies.sh` against a running proxy:

```bash
# Negative test (run from a non-allowlisted host):
BASE_URL=https://staging.example.com \
HOST_HEADER=staging.example.com \
INSECURE_TLS=true \
  ./scripts/ops/verify_proxy_policies.sh
# expect: /admin and /api/v1/admin -> 403; /health -> 200; /metrics -> 401/403.

# Positive test (run from an allowlisted host):
ADMIN_ALLOWLIST_PROBE=true \
BASE_URL=https://staging.example.com \
HOST_HEADER=staging.example.com \
METRICS_BASIC_AUTH=metrics:<password> \
  ./scripts/ops/verify_proxy_policies.sh
# expect: /admin and /api/v1/admin -> NOT 403 (proxy passes through);
#         /metrics -> 200 with auth.
```

Both tests should be part of the cutover-simulation rehearsal
(`docs/ops/cutover-simulation-report-template.md`).

### What to do if an allowlist is wrong

Symptom: legitimate operators getting `403` from `/admin/*`.

1. Confirm with `verify_proxy_policies.sh ADMIN_ALLOWLIST_PROBE=true`
   from the operator's IP.
2. Check the proxy `geo` block; add the missing CIDR.
3. Reload nginx (`nginx -s reload`); no app-side changes needed.
4. Re-run the verify script.

If the misconfig was that the allowlist was *too permissive* (e.g.
`0.0.0.0/0` slipped in), follow `docs/ops/emergency-auth-ops.md` —
treat it as a potential session compromise and rotate.
