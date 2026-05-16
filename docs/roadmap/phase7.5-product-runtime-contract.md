# Phase 7.5 — Product / legal / runtime contract

Status: **next** (documentation and small README alignment — **not** a large rewrite).

**Purpose:** Fix the business and engineering contract **before** Phase 8 checkout and real payments. Readable by developers, operators, future-you, and compliance/legal reviewers.

**Do not implement** checkout in this phase.

---

## Token model

| Rule | Detail |
|------|--------|
| Scale | **`TOKEN_UNIT_SCALE = 1000`** → **1 visible token = 1000 `token_units`** |
| Balance source of truth | **`token_accounts.balance_units`** (integer) |
| Ledger source of truth | **`ledger_entries.delta_units`** (integer) |
| Runtime math | Active economy/game paths use **units only**, not float |
| Legacy float | If columns remain, they are **compatibility mirrors only** until removed — not authoritative |

Display in Telegram/UI may show visible tokens; conversion uses explicit helpers (e.g. `token_amounts` / settings scale).

---

## Game access

| Rule | Detail |
|------|--------|
| Gate | **`balance_units >= GAME_ACCESS_MIN_TOKENS * TOKEN_UNIT_SCALE`** |
| Reject code | **`access_tokens_required`** |
| Enforcement | Shared game entry path (`games/service.py` / policy), **not** Telegram-only |
| Subscription | **`user_has_active_subscription` / entitlement is not a game gate** |

Per-game stake limits (`COIN_FLIP_MIN_BET`, `BONUS_WHEEL_MIN_BET`, etc.) still apply after the access gate.

---

## Commercial model (target, Phase 8+)

| Rule | Detail |
|------|--------|
| Token packages | Purchasing a package **credits fixed `token_units`** via **`economy_service`** and ledger |
| Prices (product) | £1 → 100 tokens → **100_000 units**; £5 → 1_000 tokens → **1_000_000 units**; £20 → 10_000 tokens → **10_000_000 units** |
| Implementation | See **`phase8-token-package-checkout.md`** (design before code) |

---

## Explicitly not in the current model

- No **daily access** flag or **daily automatic debit**
- No **`charge_daily_access`** or `subscription_daily_debit` metrics
- No **subscription / entitlement gate** for playing games
- No **cash-out** or token-to-money redemption unless legally cleared and implemented deliberately
- No **monetary winnings** promised in product copy unless legally cleared (non-monetary / entertainment framing per counsel)

---

## Subscriptions table (clarification)

`subscriptions` and `entitlement` may support **billing relationships**, admin testing, or future features. They **do not** replace the game access rule above unless product and legal explicitly change this document.

---

## README / ops alignment (Phase 7.5 deliverables)

- [ ] README **Domain** section links here and states game access = **units + threshold** (not subscription).
- [ ] `.env.prod.example` validated with:
  `PYTHONPATH=src python scripts/validate_env_contract.py --env-file .env.prod.example`
- [ ] No docs pointing at non-existent `scripts/ops/validate_env_contract.py`
- [ ] Optional: one-page pointer in `docs/legal/legal-product-brief-uk-phase0.md` or product note — tokens, games, no cash-out

---

## Acceptance criteria

- No contradiction between README, this doc, and `docs/roadmap/game-phase6.md`.
- New contributor understands access model in ~5 minutes.
- Lawyer/compliance reviewer can see subject matter without reading the whole codebase.

---

## After Phase 7.5

Proceed to **Phase 8 design** (`phase8-token-package-checkout.md`), then implementation.
