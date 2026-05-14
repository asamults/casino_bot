# Telegram polling — production runbook (systemd)

This document describes how to run **exactly one** long-polling worker per Telegram bot token on a typical Linux host. The HTTP API may run elsewhere (Docker, another host); the poller only needs network access to Telegram and to the **same Postgres** as the API.

## Prerequisites

- Linux with **systemd**.
- Application tree deployed to a path the service user can read (example: `/opt/casino-bot/app`).
- Python **virtualenv** (or equivalent) with project dependencies and `casino_bot` importable (`pip install -e .` or `PYTHONPATH=.../src` as in the example unit).
- **One** active poller per `TELEGRAM_BOT_TOKEN`. A second laptop, second VPS, or overlapping `docker compose run` + systemd unit with the same token causes **conflicted or duplicate** updates — stop extras immediately.

## Secrets and env file

1. Create a dedicated directory (example):

   ```bash
   sudo mkdir -p /etc/casino-bot
   sudo chown root:root /etc/casino-bot
   sudo chmod 0755 /etc/casino-bot
   ```

2. Create **`/etc/casino-bot/telegram.env`** (owner `root:casino-bot` or `casino-bot:casino-bot`, **`chmod 600`**).  
   This file must satisfy the same **`Settings`** production contract as the API (database URL, `SECRET_KEY`, JWT keys, CORS/hosts, billing flags, etc.) **plus** Telegram variables.  
   Copy from [`.env.prod.example`](../../.env.prod.example) and [telegram-polling-prod-env.example](telegram-polling-prod-env.example); replace every placeholder with real values on the host only.

3. **Never** commit `TELEGRAM_BOT_TOKEN` or other secrets. The example systemd unit uses **`EnvironmentFile=/etc/casino-bot/telegram.env`** only — no token in the unit file.

4. For **production** polling, set at minimum:

   - `ENVIRONMENT=production`
   - `TELEGRAM_BOT_ENABLED=true`
   - `TELEGRAM_BOT_TOKEN=<from @BotFather /token>`
   - `TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS` must **include** `production` (e.g. `development,staging,production` or `production` alone), or [preflight](../../src/casino_bot/telegram_bot/preflight.py) will refuse to start.

## Service user

Create an unprivileged user if needed (names must match the unit file):

```bash
sudo useradd --system --home /opt/casino-bot --shell /usr/sbin/nologin casino-bot
sudo chown -R casino-bot:casino-bot /opt/casino-bot/app
```

Adjust paths to match your deployment.

## Install the systemd unit

From the repo (or release artifact):

```bash
sudo install -m 0644 ops/systemd/casino-bot-telegram-polling.service \
  /etc/systemd/system/casino-bot-telegram-polling.service
```

Edit the installed unit if paths differ (`WorkingDirectory`, `ExecStart`, `User`, `Group`, `EnvironmentFile`, `Environment=PYTHONPATH`).

Reload systemd:

```bash
sudo systemctl daemon-reload
```

## Enable, start, stop, restart

```bash
sudo systemctl enable casino-bot-telegram-polling.service
sudo systemctl start casino-bot-telegram-polling.service
sudo systemctl stop casino-bot-telegram-polling.service
sudo systemctl restart casino-bot-telegram-polling.service
sudo systemctl status casino-bot-telegram-polling.service
```

## Logs

Follow journal logs:

```bash
sudo journalctl -u casino-bot-telegram-polling.service -f
```

Recent boot:

```bash
sudo journalctl -u casino-bot-telegram-polling.service -b --no-pager
```

Do not paste raw logs that might include Telegram request URLs (tokens can appear in path segments).

## Safe disable

```bash
sudo systemctl disable --now casino-bot-telegram-polling.service
```

## Confirm only one active poller

On the host:

```bash
systemctl status casino-bot-telegram-polling.service
pgrep -af 'casino_bot\.telegram_bot\.polling|telegram_bot\.polling'
```

Expect **one** main `python -m casino_bot.telegram_bot.polling` (plus possible transient children).  
If you also run **local dev** polling with the same token, stop one of them — they fight for `getUpdates`.

## Conflict with Docker Compose

If the **API** is in Docker publishing `:8000`, that does not start the Telegram poller unless you run polling in another container. Typical split:

- **API**: `docker compose up -d api` (orchestrated Postgres + API).
- **Telegram**: systemd on the host (or a single dedicated container) with `DATABASE_URL` pointing at reachable Postgres (host port, internal network, or managed DB).

Ensure nothing else runs **`python -m casino_bot.telegram_bot.polling`** with the **same** token (second container, CI job, laptop).

## Optional API readiness

If the HTTP API is deployed with **`GET /ready`** (existing app route), you can probe it after deploy (separate from the poller process):

```bash
curl -fsS https://api.example.com/ready >/dev/null && echo OK
```

This is optional; the poller does not start an HTTP server.

## Smoke check script

From the repo root (on the server, after configuring env and systemd):

```bash
./scripts/ops/telegram_polling_smoke.sh --env-file /etc/casino-bot/telegram.env
```

See script `--help` for options (`--skip-systemd`, optional `--api-ready-url`).

## Token rotation (leak response)

If a token is exposed: revoke or rotate via **@BotFather** (`/revoke`, `/token`), update **`/etc/casino-bot/telegram.env`**, then:

```bash
sudo systemctl restart casino-bot-telegram-polling.service
```

## Related docs

- Overview: [telegram-polling-production.md](telegram-polling-production.md)
- Local dev: [../telegram-local-run.md](../telegram-local-run.md)

## Risks (manual)

| Risk | Mitigation |
|------|------------|
| Two pollers, same token | Single systemd unit; monitor `pgrep`; document “no second instance”. |
| Weak permissions on `telegram.env` | `chmod 600`, minimal group membership. |
| DB URL points at wrong cluster | Same DB as production API for consistent ledger. |
| `TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS` omits `production` | Poller exits at preflight; fix env and restart. |
