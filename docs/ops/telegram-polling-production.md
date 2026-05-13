# Telegram polling in production (Phase 6)

## Model

- **One bot process** owns long polling (`getUpdates`). Run **exactly one** active `python -m casino_bot.telegram_bot.polling` instance per bot token in production.
- **Webhooks** are out of scope for this phase; use polling until a stable HTTPS edge and webhook ops are ready.

## systemd (recommended)

1. Run the bot as an **unprivileged** user with `WorkingDirectory` set to the app tree and `EnvironmentFile` pointing at production env (not committed).
2. Set `Restart=on-failure` and sensible `RestartSec`.
3. Log to journald (`StandardOutput=journal`) or a rotated file; do not log secrets or full Telegram URLs (token appears in API paths).

## Failure modes

- **Two instances with the same token**: Telegram may deliver updates unpredictably; users can see duplicate or missing replies. Stop duplicate units immediately.
- **DB unavailable**: handlers surface generic errors; `/status` reflects readiness separately from liveness.

## Deploy / restart

1. `systemctl stop casino-bot-telegram` (unit name as you defined it).
2. Deploy code + env.
3. `systemctl start casino-bot-telegram`.
4. Confirm a single active main PID (`systemctl status`).

For local iteration, see `docs/telegram-local-run.md`.
