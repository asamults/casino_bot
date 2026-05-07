## Production cutover readiness checklist (dry-run)

Goal: verify we can safely cut over to production **without** performing the cutover yet.

### Preflight (must pass before touching DNS/TLS)
- [ ] `git status` clean, on intended SHA/tag
- [ ] CI green on that SHA/tag (Security Gates / Smoke / Docker Smoke)
- [ ] `python scripts/validate_env_contract.py --env-file .env.prod` passes
- [ ] DB backup plan confirmed (see rollback plan)
- [ ] On-call owner assigned for the window

### DNS
- [ ] Domain chosen (e.g. `api.example.com`)
- [ ] TTL reduced in advance (e.g. 60–300s) for cutover window
- [ ] Record plan:
  - [ ] A/AAAA or CNAME target identified
  - [ ] rollback DNS target identified

### TLS / reverse proxy
- [ ] Reverse proxy config prepared (nginx/caddy/traefik)
- [ ] TLS strategy chosen:
  - [ ] Let’s Encrypt (recommended) OR
  - [ ] existing certs provisioned in secret store
- [ ] `/metrics` access policy enforced at proxy (basic auth or IP allowlist)
- [ ] Host header handling correct for TrustedHostMiddleware (`Host: api.example.com`)

### Env / secrets
- [ ] Secrets inventory reviewed: `docs/ops/secrets-inventory.md`
- [ ] Secrets present in secret store (not in repo):
  - [ ] `SECRET_KEY`, `JWT_SIGNING_KEY`, `REFRESH_TOKEN_PEPPER`
  - [ ] `USER_API_INTERNAL_TOKEN`
  - [ ] `STRIPE_WEBHOOK_SECRET` / `PADDLE_WEBHOOK_SECRET` if webhooks enabled
  - [ ] provider API keys if required for enabled features
- [ ] Rotation notes understood (what rotates, how, how to verify)

### DB migration
- [ ] `wait_for_db` passes from the app runtime environment
- [ ] `alembic upgrade head` runs cleanly (staging/prod-like environment)
- [ ] migration rollback policy understood (forward-only default)

### Smoke (via proxy / domain)
Run: `./scripts/ops/production_preflight.sh`
- [ ] `/health` 200
- [ ] `/ready` 200
- [ ] `/metrics` is blocked without auth (401/403) and allowed with auth (200)
- [ ] legacy `/admin/*` returns deprecation headers (still present until sunset)

### Rollback readiness
- [ ] Rollback procedure reviewed: `docs/ops/production-rollback-plan.md`
- [ ] Evidence retention confirmed (dead_letter / failed events are not auto-deleted)

