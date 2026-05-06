# Casino Bot

## Purpose
Casino Bot is a Python-based application designed to automate casino-related operations, including betting management, user interactions, and administrative tasks. The bot is intended for educational and development purposes, demonstrating backend development with Python, FastAPI, database integration, and REST API endpoints.

## Features
- User management and authentication via FastAPI endpoints
- Betting and game logic automation
- Admin panel for monitoring and controlling bot operations
- Database interaction using PostgreSQL or SQLite with SQLAlchemy
- Migration and rollback support with Alembic
- Logging and monitoring of critical events
- Docker support for easy deployment

## Technologies
- Python 3.11+
- FastAPI for API endpoints
- SQLAlchemy ORM for database operations
- Alembic for database migrations
- PostgreSQL or SQLite as database backend
- Docker and Docker Compose for containerization
- Uvicorn as ASGI server

## Repository language

All **repository artifacts** stay in **English**: README, inline comments, `Makefile` / CI strings, `.env.example` descriptions, OpenAPI text, and user-facing error messages in code. Day-to-day **development process** (chat, calls, issue triage) may be in Russian or another team language; keep the codebase and docs English-only for consistency and external contributors.

## Domain, compliance, and subscriptions

- **`users`**: core identity with optional `telegram_user_id` (unique), `whatsapp_phone_e164` (unique E.164 including `+`), optional `billing_customer_id` (indexed, for a future billing provider), `internal_note`, and `is_active`. Token balances live in `token_accounts` with a foreign key to `users.id`.
- **`subscriptions`**: placeholder for paid plans (`provider`, `plan_code`, `status`, `external_subscription_id`, `current_period_end`). No Stripe/Paddle SDK in this repo; webhook handlers would update rows later. Use `services.entitlement.user_has_active_subscription` for simple gating (`status == active` and period end if set).
- **Compliance**: pure rules in `casino_bot.compliance` (`Operation` + `validate_operation` registry). Token adjustments go through `economy_service` so checks run before commit; violations map to HTTP **409** on admin APIs.
- **Audit**: `audit_service.audit_log` records admin login outcomes (no passwords) and token balance changes with structured `details` JSON on `audit_logs`.
- **Telegram/WhatsApp**: only nullable columns and uniqueness; no bot clients or webhooks in this layer.

### Admin API v1 (preferred)

Base path: **`/api/v1/admin`** (OpenAPI “Authorize” uses `POST /api/v1/admin/login`). JWT `role` is either **`admin`** or **`superadmin`** (`superadmin` can manage staff accounts and activate internal test subscriptions).

List endpoints return **`{ "items": [...], "total": N }`**. Compliance violations return **409** with JSON `{"detail": "...", "code": "COMPLIANCE_VIOLATION"}`.

Replace host/port and credentials as needed (`ADMIN_EMAIL` / `ADMIN_PASSWORD` must exist in `admin_users`).

```bash
TOKEN=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/admin/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=ADMIN_EMAIL&password=ADMIN_PASSWORD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

curl -s "http://127.0.0.1:8000/api/v1/admin/users?skip=0&limit=20" \
  -H "Authorization: Bearer $TOKEN"

curl -s -X POST "http://127.0.0.1:8000/api/v1/admin/users" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"internal_note": "demo"}'

curl -s -X POST "http://127.0.0.1:8000/api/v1/admin/users/1/tokens/adjust" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"delta": 10.0, "reason": "welcome_bonus"}'

curl -s "http://127.0.0.1:8000/api/v1/admin/audit-logs?skip=0&limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

**Legacy:** the same JWT works with **`/admin/login`**, **`/admin/users`**, etc., for one transition release; new integrations should use **`/api/v1/admin/...`**.

**CORS (future SPA):** not enabled by default. When you add a browser admin UI on another origin, configure `CORSMiddleware` in `main.py` with explicit `allow_origins` (e.g. `https://admin.example.com`) instead of `*` if credentials are used.

## Repository Structure

casino_bot/
├── alembic/ # Database migrations
├── app/ # Application source code
│ ├── api/ # API endpoints
│ ├── core/ # Core business logic
│ ├── models/ # Database models
│ ├── services/ # Services and utilities
│ └── main.py # Entry point for FastAPI server
├── tests/ # Unit and integration tests
├── Dockerfile # Docker configuration
├── docker-compose.yml # Docker Compose for dev/testing
├── requirements.txt # Python dependencies
└── README.md # Project documentation


## Running locally and environment variables

Configure variables via the process environment or a `.env` file in the project root (see `.env.example`).

| Variable | Description |
|----------|-------------|
| `ENVIRONMENT` | `development` (default), `staging`, or `production`. In `production`, `SECRET_KEY` and `DATABASE_URL` are validated at startup: local-development placeholders are not allowed. |
| `LOG_LEVEL` | Logging level (`INFO` by default). |
| `DATABASE_URL` | SQLAlchemy database URL (e.g. PostgreSQL with `psycopg` v3). Use host **`localhost`** when you run Alembic or uvicorn **on your machine**; **`postgres`** is only valid **inside** Docker Compose (the API container resolves that service name). If Alembic errors with “failed to resolve host `postgres`”, your `.env` is set for Compose—switch `DATABASE_URL` to `localhost` for local CLI use (with Postgres reachable on port 5432). |
| `SECRET_KEY` | Secret for signing JWTs (must be unique in production, not `DEV_ONLY_CHANGE_ME`). |

From the **repository root** (the `casino_bot` project directory, not a literal `/path/to/...` path): install dependencies (`pip install -r requirements.txt`), copy `.env.example` to `.env` if needed, run migrations `alembic upgrade head`, set `export PYTHONPATH=src` (or `pip install -e .`), then `uvicorn casino_bot.main:app --reload`. If port 8000 is in use (`Address already in use`), use another port, e.g. `--port 8001`. `GET /health` is the liveness probe; `GET /ready` checks the database and is used for readiness monitoring and the Docker Compose API healthcheck.

Tests: `pytest` (`pyproject.toml` sets `pythonpath = ["src"]`).

### Dependency hygiene (Week 1)

- **Single source of truth**: `requirements.txt` is installed the same way in **Docker** (`Dockerfile`), **CI** (GitHub Actions), and local dev.
- **Local setup**: create a venv, then upgrade installers and install pins:
  ```bash
  python3 -m venv .venv && source .venv/bin/activate
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install --no-cache-dir -r requirements.txt
  ```
- **Supply chain checks** (after install): `ruff check .`, `ruff format --check .`, `pytest`, `bandit -r src -ll`, `pip-audit --progress-spinner off`, `alembic upgrade head` (with a reachable Postgres matching `DATABASE_URL`).
- **Automation**: [Dependabot](.github/dependabot.yml) opens weekly PRs for `requirements.txt` and periodic PRs for GitHub Actions. Merge only when CI is green.
- **Docker parity**: `docker compose build` uses the same `requirements.txt` copy + `pip install -r requirements.txt` as CI (see `Dockerfile`).

If Alembic reports **`password authentication failed for user "casino"`**, the username/password in `DATABASE_URL` do not match the running Postgres instance. For the Postgres service in this repo’s `docker-compose.yml`, the defaults are **user `casino`**, password **`secret`**, database **`casino_db`** (`postgresql+psycopg://casino:secret@localhost:5432/casino_db` on the host). If you use another Postgres install or changed `POSTGRES_PASSWORD`, update `.env` to match—or reset the Compose volume (`docker compose down -v`) only if you accept losing that database’s data.

## Security (Layer 4)

### Authentication model (access + refresh)

- `POST /api/v1/admin/login` and legacy `POST /admin/login` now return:
  - short-lived `access_token` (`type=access`, claims: `sub`, `role`, `iat`, `exp`, `jti`)
  - `refresh_token` (`type=refresh`, claims: `sub`, `sid`, `iat`, `exp`)
- `POST /api/v1/admin/refresh` (and legacy `/admin/refresh`) performs rotation:
  - old refresh session is revoked
  - a new session row and new token pair are issued
  - old refresh token reuse is rejected
- `POST /api/v1/admin/logout` revokes one session.
- `POST /api/v1/admin/logout-all` revokes all active sessions for current admin; `superadmin` may pass `admin_user_id` to revoke another admin.
- Access-only legacy behavior is supported for one transition release; integrations should migrate to refresh flow.

### Session storage and revocation

- Persistent sessions are in `admin_sessions`.
- Refresh tokens are never stored plaintext; DB contains only `refresh_token_hash` (HMAC-SHA256 using `REFRESH_TOKEN_PEPPER`).
- Revocation is immediate for refresh endpoint checks.
- Audit events include: `login_success`, `login_failed`, `refresh`, `logout`, `logout_all`, and lockout events.

### Brute-force lockout policy

- Login attempts are tracked in `admin_login_locks`.
- Config:
  - `MAX_LOGIN_ATTEMPTS` (default `5`)
  - `ATTEMPT_WINDOW_SECONDS` (default `300`)
  - `LOCKOUT_SECONDS` (default `900`)
- Lockout returns `429 Too Many Requests`.
- Login error message stays generic (`Invalid credentials`) to avoid account enumeration.

### Rate limiting, CORS, and headers

- In-memory per-minute limits (configurable):
  - login: `LOGIN_RATE_LIMIT_PER_MINUTE`
  - refresh: `REFRESH_RATE_LIMIT_PER_MINUTE`
  - admin reads: `READ_RATE_LIMIT_PER_MINUTE`
  - admin writes: `WRITE_RATE_LIMIT_PER_MINUTE`
- Responses include `X-RateLimit-*` headers.
- Production settings reject wildcard CORS and require explicit `CORS_ALLOW_ORIGINS`.
- `TrustedHostMiddleware` is enabled in production using `ALLOWED_HOSTS`.
- Security headers are always returned:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'`

### Secret policy and rotation

- Required secrets:
  - `JWT_SIGNING_KEY` (JWT signing)
  - `REFRESH_TOKEN_PEPPER` (refresh token hashing)
  - `DATABASE_URL`
  - `SECRET_KEY` (legacy transition compatibility only; keep strong/random)
- Production startup fails fast when:
  - dev defaults are used
  - secret length is below 32 chars
  - CORS origins/allowed hosts are insecure or missing
- Rotation strategy:
  - rotate `JWT_SIGNING_KEY` and `REFRESH_TOKEN_PEPPER` on schedule and incident response
  - use staged deploy with short access-token TTL and forced session revocation for emergency response
  - optional next step: `kid`-based multi-key JWT verification for graceful key rollover

### Security runbook (short)

- Suspected refresh token leak:
  - revoke affected session (`/logout`) or revoke all (`/logout-all`)
  - force password reset for impacted admin
  - monitor audit stream for repeated refresh failures/reuse attempts
- Signing key compromise:
  - rotate `JWT_SIGNING_KEY` immediately
  - revoke all admin sessions
  - redeploy with new secrets and verify `/api/v1/admin/refresh` rejects old tokens
- Mass revoke:
  - as superadmin call `/api/v1/admin/logout-all` with target `admin_user_id` as needed

### Local security checks

```bash
alembic upgrade head
pytest -q
ruff check src tests
bandit -r src -ll
pip-audit --progress-spinner off
```

## Billing Webhooks Foundation (Layer 4.1)

### Environment variables

- `BILLING_PROVIDER_PRIMARY` = `stripe` or `paddle`
- `BILLING_ENABLE_WEBHOOKS` = `true|false`
- `BILLING_FAIL_ON_MISSING_SECRETS_IN_PROD` = `true|false` (default `true`)
- `STRIPE_WEBHOOK_SECRET`
- `PADDLE_WEBHOOK_SECRET`
- `ENTITLEMENT_GRACE_SECONDS` (optional grace after period end)
- `ENTITLEMENT_ENFORCEMENT_MODE` = `hard|soft` (`soft` logs-only behavior for staged rollout)

In production, if webhooks are enabled and the primary provider secret is missing, startup fails fast.

### Endpoints

- `POST /api/v1/billing/webhooks/stripe`
- `POST /api/v1/billing/webhooks/paddle`
- `GET /api/v1/admin/billing/events` (superadmin, metadata only)
- `POST /api/v1/admin/users/{id}/subscription/link-test` (superadmin, test linking)
- `POST /api/v1/admin/users/{id}/subscription/deactivate-test` (superadmin)

### Idempotency and sync behavior

- Incoming events are stored in `billing_webhook_events` with unique `(provider, external_event_id)`.
- Duplicate delivery returns 200 with `{"status":"idempotent"}`.
- Unknown/unsupported events are marked `ignored` (200).
- Unresolved user mapping is marked `failed` and audited.
- Successful processing upserts `subscriptions` and updates `entitlement_active`.

### Linking strategy

Webhook-to-user mapping priority:
1) `metadata.user_id`
2) `provider_customer_id`/`billing_customer_id` match
3) otherwise fail safely (no silent wrong link)

### Entitlement gate

`require_active_entitlement(user_id)` is applied to paid business operation `POST /api/v1/admin/users/{id}/tokens/adjust`.
Without entitlement, API returns `402` with code `ENTITLEMENT_REQUIRED`.

### Local webhook tests

```bash
pytest -q tests/test_billing_webhooks.py
```

### Dev webhook flow example (Stripe test payload)

1. Prepare JSON payload and local signature:

```bash
BODY='{"id":"evt_local_1","type":"customer.subscription.updated","created":1700000000,"data":{"object":{"id":"sub_local_1","customer":"cus_123","status":"active","cancel_at_period_end":false,"current_period_end":1999999999,"items":{"data":[{"price":{"lookup_key":"pro_monthly"}}]},"metadata":{"user_id":"101"}}}}'
TS=1700000000
SIG=$(python3 - <<'PY'
import hashlib,hmac,os
secret=os.environ.get("STRIPE_WEBHOOK_SECRET","whsec_test_secret")
ts=os.environ.get("TS","1700000000")
body=os.environ["BODY"]
print(hmac.new(secret.encode(), f"{ts}.{body}".encode(), hashlib.sha256).hexdigest())
PY
)
curl -s -X POST "http://127.0.0.1:8000/api/v1/billing/webhooks/stripe" \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: t=$TS,v1=$SIG" \
  -d "$BODY"
```

### Billing runbook (short)

- Webhook backlog:
  - check `GET /api/v1/admin/billing/events?status=failed`
  - resolve mapping failures (link customer/subscription IDs), then replay provider events
- Duplicate storm:
  - expected to be safe due to unique event key; monitor DB/API load and rate-limit upstream retries
- Webhook secret rotation:
  - rotate secret in provider dashboard + env secret store
  - deploy, verify signature pass on new events, retire old secret
- Safe replay:
  - replay from provider side is safe; duplicates are acked idempotently

## Monetization Layer 5

### Billing API quickstart

- Checkout session: `POST /api/v1/billing/checkout/session`
- Self subscription read: `GET /api/v1/billing/me/subscription`
- Self cancel/resume: `POST /api/v1/billing/me/subscription/cancel`, `POST /api/v1/billing/me/subscription/resume`
- Customer portal link: `POST /api/v1/billing/me/portal`
- Replay tooling (superadmin): `POST /api/v1/admin/billing/events/{id}/replay`, `POST /api/v1/admin/billing/events/replay-failed`
- Billing metrics (superadmin): `GET /api/v1/admin/billing/metrics`

### Layer 5 environment variables

- `BILLING_ENABLE_CHECKOUT` (feature flag)
- `BILLING_ALLOWED_PLANS` (server-side whitelist)
- `BILLING_ALLOWED_RETURN_HOSTS` (redirect host allowlist)
- `USER_API_INTERNAL_TOKEN` (internal user-side API auth)
- `BILLING_WEBHOOK_TOLERANCE_SECONDS` (signature freshness window)
- `BILLING_DEAD_LETTER_ATTEMPTS`
- `BILLING_WEBHOOK_RETENTION_DAYS` (retention policy input)
- `BILLING_POLICY_TOS_URL`
- `BILLING_POLICY_REFUND_URL`
- `BILLING_POLICY_CANCELLATION_URL`
- `STRIPE_API_KEY`, `PADDLE_API_KEY` (no live keys in repo/tests)

### Entitlement mode and policy

- `ENTITLEMENT_ENFORCEMENT_MODE=soft` for canary/log-only staging.
- `ENTITLEMENT_ENFORCEMENT_MODE=hard` for full paywall enforcement.
- Policy map is centralized in `services/entitlement_policy.py`.
- Superadmin emergency override is supported for admin service operations (token adjust).

### Secondary provider limitation

- Primary provider is selected by `BILLING_PROVIDER_PRIMARY`.
- Secondary adapter remains contract-complete but may return structured `PROVIDER_NOT_IMPLEMENTED` (`501`) for unsupported runtime operations.

### Webhook incident response

- Duplicate storm: safe by DB idempotency key `(provider, external_event_id)`.
- Replay procedure:
  - inspect `GET /api/v1/admin/billing/events?status=failed`
  - replay one event or batch failed events
  - watch dead-letter events (`dead_letter=true`)
- Retention:
  - `billing_webhook_events` is operational data; keep for `BILLING_WEBHOOK_RETENTION_DAYS`
  - cleanup only deletes terminal safe statuses: `processed`, `ignored`, `idempotent` (not `failed` / `dead_letter`)
  - manual cleanup: `DATABASE_URL=... python scripts/billing_cleanup.py`
- Failed payments spike:
  - verify provider status page / API health
  - keep entitlement grace via `ENTITLEMENT_GRACE_SECONDS`
  - switch to soft mode temporarily if needed
- Provider outage mode:
  - keep existing entitlements during grace window
  - process backlog via replay when provider recovers

## Installation and Setup
1. Clone the repository:
```bash
git clone https://github.com/asamults/casino_bot.git
cd casino_bot

    Create and activate a virtual environment:

python3 -m venv .venv
source .venv/bin/activate

    Install dependencies:

pip install -r requirements.txt

    Configure environment variables (database URL, secret keys, etc.) as required.

    Apply database migrations:

alembic upgrade head

    Run the server:

uvicorn casino_bot.main:app --reload

    Access admin endpoints via /admin routes or other defined API endpoints.

Testing

    Unit and integration tests are located in the tests/ directory.

    Run tests using:

pytest

Deployment

    The project supports Docker deployment:

docker-compose up --build

    Make sure environment variables are configured inside .env for production or development.

Contributing

    Fork the repository and create a new branch for features or bug fixes.

    Ensure all code follows PEP8 style and passes tests.

    Submit pull requests with descriptive commit messages.

License

This project is for educational and development purposes. Usage in production or real gambling applications is not recommended and should comply with all applicable legal regulations.