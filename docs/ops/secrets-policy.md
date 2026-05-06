## Secrets policy (baseline)

### Principles

- No secrets in git.
- Production uses a secret manager (preferred) or the deployment platform secret store.
- Rotate secrets on schedule and on incident response.

### What is a secret here

- `DATABASE_URL`
- `SECRET_KEY`
- `JWT_SIGNING_KEY`
- `REFRESH_TOKEN_PEPPER`
- `USER_API_INTERNAL_TOKEN`
- Billing secrets:
  - `STRIPE_WEBHOOK_SECRET` / `PADDLE_WEBHOOK_SECRET`
  - `STRIPE_API_KEY` / `PADDLE_API_KEY`

### Storage options

- Container platforms: inject as environment variables from the platform secret store.
- Docker: use environment variables from an external `.env` (not committed) or Docker secrets.

### Rotation checklist

- **JWT signing key compromise**:
  - rotate `JWT_SIGNING_KEY`
  - revoke sessions (operationally)
  - redeploy; verify admin login/refresh behavior
- **Refresh pepper compromise**:
  - rotate `REFRESH_TOKEN_PEPPER`
  - revoke all refresh sessions (since hashes become invalid)
- **Webhook secret rotation**:
  - rotate provider secret in dashboard + secret store
  - deploy; verify webhook signature acceptance

### Production guards

Production startup fails fast when:
- dev defaults are used for critical secrets
- weak secrets are configured (<32)
- drill flags are present

