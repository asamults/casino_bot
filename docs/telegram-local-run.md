# Telegram bot — local polling

This repo ships an **optional** Telegram adapter that connects with the same Postgres database as the FastAPI API. Nothing in the HTTP app requires a Telegram token; the bot runs as a **separate OS process** (`python -m casino_bot.telegram_bot.polling`).

## Why `python-telegram-bot` (not aiogram)?

Both libraries are viable for Telegram Bot API bots. Here we chose [**python-telegram-bot**](https://python-telegram-bot.org/) (PTB) **21.x** because:

- **Small surface for a polling-only worker** — a handful of command handlers and a single `Application.run_polling()` entrypoint are easy to follow and test.
- **First-class long polling** with clear lifecycle and error handling in one place.
- **Straightforward handler testing** — command logic is split into plain functions plus thin async wrappers, so unit tests do not need to open network sockets or mock aiogram’s router stack.

aiogram 3.x is excellent for larger async apps and router composition; we can revisit if the bot grows into a complex conversational flow tightly coupled to asyncio patterns.

---

## Create a bot (BotFather)

1. Open Telegram and chat with `@BotFather`.
2. Send `/newbot`, pick a display name and a username ending in `bot`.
3. Copy the **HTTP API token** BotFather returns (looks like `123456789:AAHxxxxxxxx...`).
4. **Never commit this token.** Keep it only in your local `.env` or secret manager.

---

## Configure environment

In your **`.env`** (copy from [.env.example](../.env.example)) set:

```bash
# Must be the actual value from @BotFather (/token), like `123456789:AAH…`.
# Do not use documentation placeholders (e.g. `TOKEN_FROM_BOTFATHER`).
TELEGRAM_BOT_TOKEN=your_token_from_botfather
TELEGRAM_BOT_ENABLED=true
# Default allows only development and staging polling:
# TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS=development,staging
#
# Optional /support reply (both empty → generic “contact your operator” line in the bot):
# TELEGRAM_SUPPORT_TEXT=First line\nSecond line
# SUPPORT_CONTACT_URL=https://example.com/support
```

- **`TELEGRAM_BOT_ENABLED`** defaults to `false`. The polling runner exits unless it is **`true`** and the token is set, even in development — this avoids silently opening Telegram when you only meant to run the API tests.
- **`TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS`** defaults to **`development,staging`**. **`production` is excluded** until you deliberately change this list — so prod cannot accidentally attach a polling bot when someone only sets `TELEGRAM_BOT_TOKEN`.
- **`TELEGRAM_SUPPORT_TEXT`** — optional multi-line copy for `/support`. In a single-line `.env` value you can use a literal `\n` sequence; it is turned into a real newline at load time. Leave empty for the built-in generic support line.
- **`SUPPORT_CONTACT_URL`** — optional URL shown on `/support` after any `TELEGRAM_SUPPORT_TEXT`. Leave empty if you do not want a link in the reply. Do not commit real production contacts in repo defaults.

FastAPI and tests load `Settings` without requiring `TELEGRAM_BOT_TOKEN`.

---

## Start Postgres

From the repo root, if you use the default Compose database (see `docker-compose.yml`):

```bash
docker compose up -d postgres
```

(or use any Postgres reachable by your `DATABASE_URL`).

---

## Run migrations

```bash
export PYTHONPATH=src
export DATABASE_URL=postgresql+psycopg://casino:secret@localhost:5432/casino_db
python scripts/wait_for_db.py --timeout-seconds 30
alembic upgrade head
```

---

## Start FastAPI (optional for basic bot commands)

The polling bot reads the database directly. You still typically run the API in another terminal for parity with prod:

```bash
export PYTHONPATH=src
uvicorn casino_bot.main:app --reload --host 0.0.0.0 --port 8000
```

Smoke checks:

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
```

---

## Start the Telegram polling runner

Requires the same **`DATABASE_URL`** and **`PYTHONPATH=src`** as the API:

```bash
export PYTHONPATH=src
export DATABASE_URL=postgresql+psycopg://casino:secret@localhost:5432/casino_db
export TELEGRAM_BOT_TOKEN='<paste token>'
export TELEGRAM_BOT_ENABLED=true
python -m casino_bot.telegram_bot.polling
```

If **`TELEGRAM_BOT_TOKEN` is missing**, the process prints a clear error and exits (`SystemExit`). If **`TELEGRAM_BOT_ENABLED` is false**, it exits without contacting Telegram.

---

## Test from a real Telegram account

Open your bot’s chat (the username from BotFather) and try:

| Command   | Expected behaviour |
|----------|---------------------|
| `/start` | Creates or loads a **`users`** row with your `telegram_user_id`, commits, and replies with welcome text including **internal user id**. |
| `/help` | Lists available commands (including **`/status`**, **`/profile`**, **`/admin`**, **`/support`**). |
| `/me`   | Shows Telegram id plus internal user id if linked (after **`/start`**). |
| `/balance` | Shows token balance when a **`token_accounts`** row exists; otherwise a **safe message** (`Balance unavailable …`) rather than crashing. |
| `/status` | Short **liveness vs database readiness** summary (aligned with **`GET /health`** / **`GET /ready`** semantics; no HTTP call to localhost). |
| `/profile` | Linked account fields only (**internal id**, Telegram id, **active** flag, **created** timestamp). Prompts **`/start`** if not linked. |
| `/admin` | Static pointer to the **HTTP Admin API** (`/api/v1/admin/`, documented in README); **no admin actions** in Telegram. |
| `/support` | **`TELEGRAM_SUPPORT_TEXT`** and/or **`SUPPORT_CONTACT_URL`** when set; otherwise a **generic operator** line (no baked-in production contacts). |

**Security note:** Logs record only **command name**, **telegram user id**, and **internal user id** when known — not bot tokens or full webhook/update payloads.

**Scope:** No gameplay, deposits, withdrawals, or other money-moving flows are implemented here.

---

## Command sequence recap (local laptop)

```bash
cd casino_bot
cp .env.example .env   # if needed; add TELEGRAM_* as above

docker compose up -d postgres
export PYTHONPATH=src
export DATABASE_URL=postgresql+psycopg://casino:secret@localhost:5432/casino_db
python scripts/wait_for_db.py --timeout-seconds 30
alembic upgrade head

uvicorn casino_bot.main:app --reload --host 0.0.0.0 --port 8000

# Separate terminal:
export TELEGRAM_BOT_TOKEN='...'
export TELEGRAM_BOT_ENABLED=true
python -m casino_bot.telegram_bot.polling
```
