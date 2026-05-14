# Telegram polling in production (Phase 6 / 6D)

## Model

- **One bot process** owns long polling (`getUpdates`). Run **exactly one** active `python -m casino_bot.telegram_bot.polling` instance per bot token in production.
- **Webhooks** are out of scope for this phase; use polling until a stable HTTPS edge and webhook ops are ready.

## Where to go next

- **Install, systemd, journalctl, duplicate-poller warnings, Docker vs host:**  
  [telegram-polling-production-runbook.md](telegram-polling-production-runbook.md)
- **Example unit file (copy to `/etc/systemd/system/`):**  
  [`ops/systemd/casino-bot-telegram-polling.service`](../../ops/systemd/casino-bot-telegram-polling.service)
- **Host env fragment (Telegram keys; merge with full prod `Settings`):**  
  [telegram-polling-prod-env.example](telegram-polling-prod-env.example)
- **Deploy smoke (env + optional systemd + optional `/ready` curl):**  
  [`scripts/ops/telegram_polling_smoke.sh`](../../scripts/ops/telegram_polling_smoke.sh)

## Failure modes

- **Two instances with the same token:** Telegram may deliver updates unpredictably; users can see duplicate or missing replies. Stop duplicate units immediately.
- **DB unavailable:** handlers surface generic errors; the HTTP API’s **`GET /ready`** (if deployed) reflects DB readiness separately from the poller.

## Metrics

If the API is already deployed with Prometheus scraping, **`GET /metrics`** on that host is unchanged — this phase does not add a new metrics stack. The poller process does not expose HTTP.

## Local development

See [../telegram-local-run.md](../telegram-local-run.md).
