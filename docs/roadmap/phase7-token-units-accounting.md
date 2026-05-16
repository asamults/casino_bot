# Phase 7 — Integer `token_units` accounting

Status: **closed** (merged PR #24, tag `phase7-token-units-accounting-green-2026-05-15`, example HEAD `8ee9503`).
**Next:** operational and product steps in `current-program-status.md` (VPS 6D rehearsal → Phase 7.5 → Phase 8 design/implementation).

Historical spec below (for implementers auditing the change). **Do not** reintroduce float as source of truth.

## Repository baseline (when starting — historical)

- `main` includes Phase 6D (production Telegram polling docs/unit/smoke), merged (e.g. PR #23, commit `bee669b` or later).
- Phase 6 balance gate: `GAME_ACCESS_MIN_TOKENS`, reject `access_tokens_required`.
- Game access is **balance-only**; no entitlement in `games/`, `telegram_bot/`, `game_round_service`.

## Product decision

Use **internal integer token units** instead of float for balances, stakes, ledger amounts, and payouts.

| Concept | Definition |
|---------|------------|
| Visible token | User-facing unit (e.g. “1 token”, “10.5 tokens” display only at boundaries). |
| Internal unit | Integer `token_units` stored in DB and used in all economy math. |
| `TOKEN_UNIT_SCALE` | How many units equal **one** visible token. **Chosen default: `1000`**. |

Why **1000** not **100**:

- Scale **100** supports **0.01** visible-token precision.
- Scale **1000** supports **0.001** visible-token precision — safer for wheel-style payouts without blowing up integer magnitude in practice.

Examples (`TOKEN_UNIT_SCALE = 1000`):

| Visible | `token_units` |
|---------|----------------|
| 100 tokens | `100_000` |
| 1,000 tokens | `1_000_000` |
| 10,000 tokens | `10_000_000` |
| 1 token stake | `1_000` |
| 0.5 token win | `500` |

## Invariants

1. Balance is stored as integer **`balance_units`** (name may vary; must be BIGINT-safe).
2. Ledger movement amounts are integer **`amount_units`**.
3. Runtime economy math **does not** use `float` for balance, stake, payout, or ledger.
4. User/API inputs are converted to units **at the boundary** with explicit validation.
5. No NaN / Inf; no implicit rounding in hot paths.
6. Sum of ledger lines for a user (definition in implementation) **matches** `balance_units` invariants under tests.
7. **Checkout credits** (future) only ever credit **integer units** — **no checkout in Phase 7**.
8. Game stake / win / loss only moves **integer units**.

## Settings

Add (example):

```text
TOKEN_UNIT_SCALE=1000
```

`GAME_ACCESS_MIN_TOKENS` gate after Phase 7 (conceptually):

```text
balance_units >= GAME_ACCESS_MIN_TOKENS * TOKEN_UNIT_SCALE
```

Reject code remains **`access_tokens_required`**.

## Migration strategy (safe order)

**Step 1 — Add columns**
Add `balance_units` on wallet table and `amount_units` on ledger (names illustrative). **Keep** existing float columns temporarily.

**Step 2 — Backfill**
Convert with an **explicit** policy: e.g. half-up to integer units, reject NaN/Inf, reject precision beyond supported scale. For pilot/dev with little data, `round(old * TOKEN_UNIT_SCALE)` may be acceptable if documented and verified by tests.

**Step 3 — Switch application code**
All writes/reads for economy use `*_units`. Float columns become read-only or unused for one release.

**Step 4 — Tests**
See “Required tests” below.

**Step 5 — Drop float columns**
Separate commit **only** after green CI and data verification.

## Allowed to change

- DB models / Alembic migrations
- `services/economy_service.py`
- `services/game_round_service.py`
- `games/service.py`, `games/policy.py`, `games/application_models.py`
- Telegram **presentation** formatting (display conversion only)
- `settings.py`, tests, `docs/roadmap/`

## Do not change (Phase 7)

- Checkout / payment implementation (none yet or wire later)
- New games
- Large admin redesign
- Telegram **systemd** / polling unit (unless env vars need documenting for units)
- Introduce `daily_access`, `charge_daily_access`, `subscription_daily_debit`
- Subscription/entitlement inside game execution paths

## Helper module

Add a small module, e.g. `services/token_amounts.py` (or `casino_bot/compliance/token_amounts.py`), with:

- `tokens_to_units(...)` — explicit, validated
- `units_to_display_string(...)` — for UX only
- `validate_units(...)` — reject invalid / over-precision inputs

Prefer **Decimal or str/int at boundaries**; persist and compute with **`int` only**.

## Required tests

- Package scale examples map to exact integer units.
- `GAME_ACCESS_MIN_TOKENS` gate uses **units**.
- Coin flip stake debit is integer units.
- Bonus wheel payout is deterministic integer units.
- Ledger sum invariant vs `balance_units` after multiple rounds.
- Duplicate idempotency does not double-apply units.
- Invalid fractional precision rejected at boundary.
- Grep invariants unchanged:
  - no `daily_access` / `charge_daily_access` / `subscription_daily_debit`
  - no entitlement imports in `games/`, `telegram_bot/`, `game_round_service`

## Verification commands (after implementation)

```bash
ruff check .
ruff format --check .
pytest -q
PYTHONPATH=src python scripts/validate_env_contract.py --env-file .env.prod.example
```

Sanity grep (human-run; tune patterns as needed):

```bash
grep -R "float" -n src/casino_bot | grep -E "balance|amount|stake|payout|ledger" || true
grep -R "daily_access\|charge_daily_access\|subscription_daily_debit" -n src tests --exclude-dir="__pycache__" || true
grep -R "entitlement\|require_active_entitlement\|enforce_if_required\|user_has_active_subscription" -n \
  src/casino_bot/games \
  src/casino_bot/telegram_bot \
  src/casino_bot/services/game_round_service.py \
  --exclude-dir="__pycache__" || true
```

## Branch

```bash
git checkout main
git pull --ff-only origin main
git checkout -b phase7-token-units-accounting
```

---

## Cursor / agent prompt (copy-paste)

You are working in the `casino_bot` repository.

**Current confirmed state:**

- `main` latest includes **Phase 6D: production Telegram polling runtime** (merged, e.g. PR #23, commit `bee669b` or newer).
- Phase 6 balance-based game access is closed and tagged.
- Phase 6D production Telegram polling runtime is closed and tagged (`phase6d-prod-telegram-polling-green-2026-05-14` or equivalent).
- Game access must remain **balance-based** via `GAME_ACCESS_MIN_TOKENS` (expressed in **token_units** after this phase).
- No checkout/payment implementation in **this** phase.

**Goal:** Implement **Phase 7: integer `token_units` accounting**.

**Product decision:** Use internal integer token units instead of float balances/amounts. Set **`TOKEN_UNIT_SCALE=1000`**: 1 visible token = 1000 `token_units`; 100 / 1000 / 10000 visible-token packages map to exact integer units as in `docs/roadmap/phase7-token-units-accounting.md`.

**Architecture requirements:**

1. Runtime economy math must **not** use `float` for balances, stakes, ledger amounts, or payouts.
2. Store balances and ledger movements as **integer** `token_units` columns.
3. Add migration(s): new columns, backfill, then switch code; drop float columns only in a **later** commit after green tests.
4. Preserve deterministic **idempotency**.
5. Preserve Phase 6 balance gate: `balance_units >= GAME_ACCESS_MIN_TOKENS * TOKEN_UNIT_SCALE`; reject code **`access_tokens_required`**.
6. Do **not** introduce subscription/entitlement into game execution.
7. Do **not** implement checkout in this phase.
8. Do **not** add new games.
9. Keep Telegram as adapter/presentation only.
10. Add tests proving **no float drift** and **ledger/balance consistency**.

**Implementation guidance:** Add `services/token_amounts.py` (or similar) with explicit `tokens_to_units`, display helpers, and `validate_units`. Use Decimal or string/int at boundaries; **int only** internally. Legacy float fields may remain temporarily for migration; active logic uses `*_units`.

**After implementation run:** `ruff check .`, `ruff format --check .`, `pytest -q`, and the grep block above.

**Return:** files changed, migrations, exact data model changes, test output, remaining float/accounting risks.

---

## Handoff checklist

- [ ] Migrations listed in PR description
- [ ] Display formatting documented (visible vs units)
- [ ] No secrets committed
- [ ] `docs/roadmap/current-program-status.md` reflects deployment on each environment
