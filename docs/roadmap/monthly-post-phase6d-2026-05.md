# Monthly roadmap (post Phase 6D) — May 2026 window

## Confirmed repository state (authoritative)

- **`main`** includes **Phase 6D: production Telegram polling runtime** merged via **PR #23** (example HEAD: `bee669b`).
- **Phase 6** (balance-based game access) is closed and tagged (e.g. `phase6-balance-access-green-2026-05-14`).
- **Phase 6D** is closed and tagged: **`phase6d-prod-telegram-polling-green-2026-05-14`**.
- Game access remains **balance-based** via `GAME_ACCESS_MIN_TOKENS` and reject code **`access_tokens_required`**.
- No `daily_access` / `charge_daily_access` / `subscription_daily_debit` in runtime paths; **no** subscription/entitlement in `games/`, `telegram_bot/`, or `game_round_service`.

This roadmap assumes **PR #23 is already merged**; Week 1 is **not** “open a PR”, it is **VPS rehearsal / production rollout** of that merged work.

---

## North star

```text
Phase 6D merged & tagged
→ VPS polling rehearsal (prove prod runtime)
→ Phase 7 integer token_units accounting (no float on money-adjacent paths)
→ README / legal / product contract cleanup (clarity before money)
→ Token package checkout (credits integer units via ledger only)
→ Prod API hardening, alerts, release hygiene
```

**Hard rule until Phase 7 is complete:**

- **No** checkout / payment implementation that credits user balances.
- **No** real customer payments.
- **Do not** promise exact balances while float drift is possible in production paths.

After Phase 7, checkout is linear:

```text
GBP payment → package id → fixed token_units credit → economy_service → audit → balance_units
```

---

## Week 1 — VPS polling rehearsal

**Goal:** prove production Telegram polling actually works on a real host.

| Activity | Done when |
|----------|-----------|
| Install systemd unit from repo (`ops/systemd/…`) | Unit files in place |
| Create host-only secrets file (e.g. `/etc/casino-bot/telegram.env`, mode `600`) | No secrets in git |
| `systemctl enable --now` | `systemctl is-active` succeeds |
| `journalctl` | Logs show clean startup, no crash loop |
| `scripts/ops/telegram_polling_smoke.sh` | Exits 0 |
| Single poller | Only one `telegram_bot.polling` process; no laptop dev with same token |
| Manual Telegram checks | `/help`, `/flip` or `/wheel`, `/balance` behave as expected |
| Runbook accuracy | `docs/ops/telegram-polling-production-runbook.md` matches what you did |

---

## Week 2 — Phase 7: `token_units` integer accounting

**Goal:** remove **float** from money-adjacent balances, stakes, ledger lines, and payouts.

Full spec and implementation prompt: **`docs/roadmap/phase7-token-units-accounting.md`**.

Summary:

- `TOKEN_UNIT_SCALE = 1000` → **1 visible token = 1000 `token_units`**.
- Persist **`balance_units`** / **`amount_units`** as **BIGINT** (or equivalent); runtime math **int-only**.
- Migrations: add columns → backfill with explicit rounding policy → switch code → later drop float columns.
- Preserve idempotency, Phase 6 gate (`access_tokens_required` in **units**), no checkout in Phase 7.

Branch convention: `phase7-token-units-accounting` from updated `main`.

---

## Week 3 — README / legal / product contract cleanup

**Goal:** one coherent story for engineers, support, and counsel **before** money.

| Deliverable | Done when |
|-------------|-------------|
| README (short) | Game access = `balance >= GAME_ACCESS_MIN_TOKENS` (in **units** after Phase 7); subscription/entitlement described separately, **not** as a game gate |
| Env contract | `.env.prod.example` aligned with `PYTHONPATH=src python scripts/validate_env_contract.py --env-file .env.prod.example` |
| Docs paths | No references to non-existent `scripts/ops/validate_env_contract.py` |
| Product / legal note | Tokens, games, no cash-out; no monetary “winnings” unless legally cleared |

**Done when:** new contributor understands access in ~5 minutes; lawyer sees a single checkable statement.

---

## Week 4 — Checkout token packages (+ prod API hardening start)

**Goal:** £1 / £5 / £20 packages credit **integer `token_units`** only, via existing billing + webhooks + **`economy_service`** only.

| Guardrail | Done when |
|-----------|-----------|
| Idempotent webhook | Duplicate provider events cannot double-credit |
| Failure paths | Cancelled/failed payment → **no** ledger credit |
| Atomicity | Ledger + audit (where applicable) consistent with balance |
| No float drift | Phase 7 complete **before** this week’s checkout work |

Parallel (same week or spillover): prod API skeleton (compose / proxy / HTTPS / `/ready` / backups), alerts after real traffic, release checklist, secret hygiene.

---

## References

- Phase 6 spec: `docs/roadmap/game-phase6.md`
- Phase 6D runbook: `docs/ops/telegram-polling-production-runbook.md`
- Phase 7 spec + agent prompt: `docs/roadmap/phase7-token-units-accounting.md`
- Game prep (historical phases): `docs/roadmap/game-development-prep.md`
