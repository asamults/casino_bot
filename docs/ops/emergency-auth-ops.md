## Emergency auth operations runbook (M6W2)

When to use this runbook:

- A privileged token (admin JWT or refresh token) is suspected leaked.
- A signing secret (`JWT_SIGNING_KEY`, `REFRESH_TOKEN_PEPPER`) is
  suspected leaked.
- A storage compromise: refresh tokens stolen from the DB at rest.
- A staff offboarding event that requires immediate session revocation.

This is a **runbook**, not a policy doc — it's about what to do at
03:00 with a phone in one hand. For the underlying secret model, see
`docs/ops/secrets-policy.md`.

### Severity matrix

| Scenario                                | Action                                                  | Downtime          |
| --------------------------------------- | ------------------------------------------------------- | ----------------- |
| Single admin's session was used by them on a wrong device | logout-all for that admin                | None              |
| Single admin's session leaked elsewhere | logout-all for that admin + password reset              | None              |
| Refresh token suspected stolen          | logout-all for affected admin(s)                        | None              |
| `REFRESH_TOKEN_PEPPER` leaked           | rotate pepper → all refresh sessions become invalid     | All admins re-login |
| `JWT_SIGNING_KEY` leaked                | rotate signing key → all access tokens become invalid   | All clients re-auth |
| Both leaked / unknown blast radius      | rotate both, logout-all globally                        | All admins re-login |

### Available endpoints (current state)

The api exposes the following revocation endpoints under both
`/api/v1/admin/*` (canonical) and `/admin/*` (legacy):

- `POST /api/v1/admin/logout`         — revoke a single refresh session
  (by `refresh_token` OR `session_id` body field).
- `POST /api/v1/admin/logout-all`     — revoke ALL refresh sessions for
  the calling admin. Superadmins can pass `admin_user_id` in the body
  to target another admin.

There is intentionally **no global "wipe all sessions"** HTTP endpoint.
That capability lives at the secret-rotation layer (see "Rotate
`REFRESH_TOKEN_PEPPER`" below) — bypassing it would be too easy a foot-gun.

### Procedure: revoke a single admin's sessions (no downtime)

You need: a superadmin access token, and the target admin's email
(or `admin_user_id`).

```bash
SUPERADMIN_TOKEN=...      # superadmin's access token
TARGET_ADMIN_USER_ID=42

curl -fsS -X POST \
  -H "Authorization: Bearer $SUPERADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"admin_user_id\": $TARGET_ADMIN_USER_ID}" \
  https://<host>/api/v1/admin/logout-all
# expect 200 with {"status":"ok","revoked_sessions":N}
```

Verify:

- Tail app logs for `admin_login` events from the target admin in the
  next 5 minutes — they MUST re-authenticate to refresh.
- The audit log table records the revocation actor and target.

### Procedure: rotate `REFRESH_TOKEN_PEPPER`

Effect: every existing refresh-token hash in the DB becomes invalid.
All admins are forced to re-login on their next access-token expiry.

What breaks:

- Active access tokens **still work** until their natural TTL (they're
  signed with `JWT_SIGNING_KEY`, not the pepper).
- Refresh attempts return 401; clients fall back to login.
- Webhook secrets / billing flows are unaffected (separate secret).

Steps:

1. Generate a new pepper (≥32 chars, high-entropy). The exact source is
   per-deployment (vault / 1Password / `openssl rand -base64 32`).
2. Update `REFRESH_TOKEN_PEPPER` in the secret store.
3. Roll the api containers (`docker compose -f docker-compose.prod.yml
   up -d --force-recreate api`).
4. Watch `casino_bot_db_ready_state` and `/ready` during the rolling
   restart.
5. Communicate to the admin team: "expect a re-login prompt in the next
   ~hour".

Rollback: revert the pepper in the secret store and re-roll. Note that
any new refresh tokens issued under the *new* pepper will become
invalid on rollback — the rollback window is "the time between the new
pepper deploy and the rollback".

### Procedure: rotate `JWT_SIGNING_KEY`

Effect: every existing access token becomes invalid immediately.

What breaks:

- All clients see 401 on their next request and must re-auth.
- The token type is `access`, scope short-lived, so the practical user
  impact is "everyone re-logs in once".
- If the api fleet is multi-instance, mid-rollout there's a brief
  window where some instances accept the old key and some only the
  new. Plan: roll all instances within < access-TTL minutes.

Steps:

1. Generate a new key (≥32 chars, high-entropy).
2. Update `JWT_SIGNING_KEY` in the secret store.
3. Roll the api fleet.
4. Watch `casino_bot_http_requests_total{status="401"}` spike briefly
   (expected) and recover (clients re-authenticated).
5. If it doesn't recover in 30 minutes, something's wrong — pull
   logs, check that `validate_env_contract.py` accepts the new value.

### Procedure: rotate both (worst case)

When the blast radius is unclear (key material exfiltrated wholesale):

1. Pre-stage both new values in the secret store.
2. Coordinate a maintenance window (5–10 minutes is enough for the
   re-login wave).
3. Roll the api fleet once with both env vars updated. Don't do two
   rolls — that doubles the re-login prompts and the operational
   window.
4. After the roll: every admin re-logs in; every refresh attempt with
   an old token returns 401.
5. File an incident report (`docs/runbooks/incident-template.md`).

### Procedure: emergency lockdown (deny all admin traffic)

If the corruption scope is unknown and you need to **stop all admin
activity right now** while you investigate:

Option A — IP allowlist to nothing (preferred, no app downtime):

```bash
# At the reverse proxy host:
sudo sed -i 's|# .* 1;|# (locked down)|' /etc/nginx/nginx.conf  # or comment all `... 1;` lines
sudo nginx -t && sudo nginx -s reload
```

`/health` and `/ready` keep responding (load balancer happy); every
`/admin/*` request gets 403 at the proxy.

Option B — toggle `LEGACY_ADMIN_DISABLE=true` for `/admin/*`. The
canonical `/api/v1/admin/*` path is unaffected, so this is a partial
lockdown only.

After the investigation:

1. Restore the allowlist or unset the env flag.
2. Reload nginx / re-roll api.
3. Run `./scripts/ops/verify_proxy_policies.sh` to confirm shape.

### Verification (after any of the above)

```bash
# Proxy/admin access works as expected:
ADMIN_ALLOWLIST_PROBE=true \
BASE_URL=https://<host> \
HOST_HEADER=<host> \
METRICS_BASIC_AUTH=metrics:<password> \
  ./scripts/ops/verify_proxy_policies.sh

# Login flow round-trips against the new keys:
curl -fsS -X POST \
  -d 'username=...&password=...' \
  https://<host>/api/v1/admin/login \
  | jq -r .access_token
```

### Audit trail expectations

Every revocation/rotation should produce evidence:

- App audit logs: `revoke_all_sessions` rows with actor + target.
- Proxy access logs: 401/403 wave during the rotation window.
- Incident note linking to this runbook + the secret-store change diff.

If any of these are missing after an incident, that itself is a
follow-up ticket: the platform's evidence quality is part of the
control.
