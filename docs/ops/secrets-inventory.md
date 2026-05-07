## Secrets inventory

This document lists required/optional secrets for production. Do **not** store real values in the repo.

### Required (production)
- `SECRET_KEY`
  - **Where**: secret store (Vault/SM/KMS/CI secrets)
  - **Notes**: must be non-default, >=32 chars
- `JWT_SIGNING_KEY`
  - **Where**: secret store
  - **Notes**: must differ from `SECRET_KEY`, >=32 chars
- `REFRESH_TOKEN_PEPPER`
  - **Where**: secret store
  - **Notes**: >=32 chars; changing invalidates stored refresh token hashes
- `USER_API_INTERNAL_TOKEN`
  - **Where**: secret store
  - **Notes**: non-default; used for internal auth between services/scripts
- `DATABASE_URL`
  - **Where**: config/secrets (depending on policy)
  - **Notes**: treat as sensitive (credentials)

### Billing webhooks (only if enabled)
- `STRIPE_WEBHOOK_SECRET`
- `PADDLE_WEBHOOK_SECRET`

### Billing API keys (only if required by enabled features)
- `STRIPE_API_KEY`
- `PADDLE_API_KEY`

### Never commit
- `.env.prod`, `.env.staging`, `.env` with real secrets
- reverse proxy `.htpasswd`
- TLS private keys/certs

### Rotation notes (high level)
- **JWT_SIGNING_KEY**: rotate with overlap strategy (if supported) or coordinated logout
- **REFRESH_TOKEN_PEPPER**: rotation invalidates refresh tokens; plan a forced re-auth window
- **Webhook secrets**: rotate in provider dashboard + deploy + verify signatures

