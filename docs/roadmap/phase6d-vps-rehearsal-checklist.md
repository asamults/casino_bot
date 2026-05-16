# Phase 6D — VPS polling rehearsal (operational proof)

**Prerequisite:** Phase 6D **implementation** is merged on `main` (systemd unit, runbook, smoke script). This checklist proves **runtime** on a real Linux host.

**Not in scope:** checkout, game logic changes, new env secrets in git.

## Host setup

- [ ] App code deployed at known `WorkingDirectory` (matches unit file).
- [ ] Python venv or interpreter path matches unit `ExecStart`.
- [ ] PostgreSQL reachable from host with production `DATABASE_URL`.
- [ ] Create **`/etc/casino-bot/telegram.env`** (mode **600**, correct owner). **No** real tokens in the repository.
- [ ] `ENVIRONMENT=production` only if production policy is intended; understand `TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS` in settings.

## systemd

- [ ] Install unit from `ops/systemd/casino-bot-telegram-polling.service` (or path documented in runbook).
- [ ] `sudo systemctl daemon-reload`
- [ ] `sudo systemctl enable --now casino-bot-telegram-polling.service`
- [ ] `systemctl status casino-bot-telegram-polling.service` → **active (running)**

## Logs and smoke

```bash
journalctl -u casino-bot-telegram-polling.service -n 100 --no-pager
./scripts/ops/telegram_polling_smoke.sh --env-file /etc/casino-bot/telegram.env
```

- [ ] Startup logs show no crash loop.
- [ ] Smoke script exits **0**.

## Single poller

```bash
ps aux | grep -E "casino_bot.telegram_bot.polling|telegram.*polling" | grep -v grep
```

- [ ] Exactly **one** polling process on this host for this bot token.
- [ ] **No** local dev machine running polling with the **same** `TELEGRAM_BOT_TOKEN`.

## Manual Telegram checks

- [ ] `/start`
- [ ] `/balance`
- [ ] `/games` (catalog)
- [ ] `/flip` or coin flip flow (committed round, balance updates in **units** after Phase 7)
- [ ] `/wheel` (bonus wheel)
- [ ] Path with balance below `GAME_ACCESS_MIN_TOKENS` → `access_tokens_required` message; balance unchanged

## Done when

- Runbook steps in `docs/ops/telegram-polling-production-runbook.md` match what you executed (note any deltas in ops notes).
- Operator can start/stop/restart and find logs without developer help.

## References

- `docs/ops/telegram-polling-production-runbook.md`
- `docs/telegram-local-run.md` (local dev vs prod)
- Program status: `current-program-status.md`
