# Game Phase 6 — Universal delivery, token access, audio cues

Status: **implemented** in repo (Phase 6). Builds on Phases 1–5 and observability Phase 4B.

## Product model (canonical)

**Purchasing tokens = commercial access to the product.** Implementation credits the user’s **token ledger** via the existing billing + economy path when checkout is wired (no new billing provider in Phase 6).

**Access to play a game = token balance threshold** `GAME_ACCESS_MIN_TOKENS` (default **1**, aligned with minimum stakes). There is **no** daily automatic debit, no `charge_daily_access`, and no `daily_access_*` / `subscription_daily_debit_*` metrics or fields in this phase.

Flow:

```text
money → token package purchase → token ledger credit → balance gate (`GAME_ACCESS_MIN_TOKENS`) → game stake / win / loss
```

- **No daily automatic debit** in Phase 6 (and not part of this spec).
- All balance changes stay on the **existing ledger / `economy_service`** path.

---

## Token access model

Buying a token package is **commercial access** to the product: checkout (when wired) credits the user’s token ledger via the existing economy path.

There is **no** daily access debit in Phase 6.

Game access is **balance-based**: a user can play only when their token balance is **at or above** `GAME_ACCESS_MIN_TOKENS`. If the balance is **below** that threshold, the game is rejected **before** stake checks and **before** any token movement for that round.

Recommended initial value: `GAME_ACCESS_MIN_TOKENS=1`, aligned with per-game minimum stakes (`COIN_FLIP_MIN_BET=1`, `BONUS_WHEEL_MIN_BET=1`): *if you can place the minimum bet, you can enter the game flow* (individual bets may still fail later for insufficient balance for a larger stake).

Stricter option (product choice): e.g. `GAME_ACCESS_MIN_TOKENS=100`.

### Package price catalog (settings / env)

Document for checkout copy and admin (no new billing provider in Phase 6):

| Package | Price (GBP) |
|---------|---------------|
| 100 tokens | £1 |
| 1,000 tokens | £5 |
| 10,000 tokens | £20 |

Suggested env names (example):

- `TOKEN_PACKAGE_100_PRICE_GBP=1`
- `TOKEN_PACKAGE_1000_PRICE_GBP=5`
- `TOKEN_PACKAGE_10000_PRICE_GBP=20`
- `GAME_ACCESS_MIN_TOKENS=1`

---

## Reject code and user copy

- **Engine / gate reject code:** `access_tokens_required` (single stable code for “cannot play due to balance vs threshold”).
- **Telegram (English, in `game_texts`):**
  - Default: `You need tokens to play games. Your balance was not changed.`
  - If surfacing the threshold explicitly: `You need at least {N} token(s) to play games. Your balance was not changed.` (with `N` = `GAME_ACCESS_MIN_TOKENS`).

**Removed from Phase 6 (do not implement):**

- Daily access debit, daily subscription charge, `DAILY_ACCESS_TOKEN_DEBIT`
- `charge_daily_access()`, `daily_access_until`, `last_daily_debit_at`
- Metrics named `subscription_daily_debit_*` or equivalent

---

## Goals

- One **channel-agnostic** application result from the game layer; Telegram is an adapter today, WhatsApp later **without** changing core game + ledger rules in `games/service.py`.
- **Balance-based** game gate at `GAME_ACCESS_MIN_TOKENS` in the **shared** entry path (not Telegram-only).
- **Token package** prices documented for product/checkout; ledger credits remain via existing economy when purchases complete.
- **Audio sequence** for `/wheel` (anticipation → result text → win/lose cue) with a **single** fallback path in `game_texts`.
- **Production Telegram**: single-instance **polling** under **systemd**; webhooks deferred until a stable HTTPS deployment endpoint exists.
- **Metrics** for game rejections (`access_tokens_required`) and audio delivery. **Canonical:** extend `casino_bot_game_round_rejected_total` with `code=access_tokens_required` (no second counter for the same reject).

## Non-goals (explicit)

- New billing provider, cash-out, P2P tokens, leaderboards, third game.
- Telegram-specific game logic inside `games/` (only adapters).
- Webhooks for Telegram in the same phase as stabilizing token gate + presentation (optional sequencing: gate first, webhook later).

---

## 6A — Universal game application layer

Introduce shared types (names indicative; adjust to repo style):

| Type | Role |
|------|------|
| `GameCommandResult` | Outcome of executing one game command: persisted round (if any), rejection, idempotent replay flag, structured details for metrics. |
| `GamePresentation` | User-facing copy + ordered **presentation steps** (text lines, optional audio cues). No Telegram types here. |
| `AudioCue` | Channel-agnostic cue descriptor: e.g. `cue_type`, `asset_id` or filesystem key, optional duration hint. |
| `BotAction` | Abstract “what the channel must do”: send message, send voice/file, edit message — **mapped in Telegram adapter only**. |

**Rule:** `games/service.py` (or a thin `games/application.py`) returns `GameCommandResult` + `GamePresentation` (+ embedded `AudioCue` / `BotAction` list). Telegram handler translates `BotAction` → python-telegram-bot calls. Future WhatsApp adapter does the same without editing game math or ledger.

---

## 6B — Balance gate (implementation note)

- In `games/service.py`, for **new** rounds only (after the idempotency-key early return for replays): load balance, compare to `GAME_ACCESS_MIN_TOKENS`, **then** cooldown, **then** stake vs balance. Access failure is **before** cooldown and stake checks.
- On failure: raise `GameEngineRejected("access_tokens_required", ...)`; **no** new `GameRound` and **no** ledger movement for that interaction.
- The **gameplay** gate is **ledger balance vs `GAME_ACCESS_MIN_TOKENS`** only (no parallel “access timer” in this phase).

---

## 6C — Audio sequence (`/wheel`)

Minimal vertical slice:

1. **Anticipation** audio cue (or fallback text only via `game_texts`).
2. **Result** text (existing formatting).
3. **Win or lose** cue (audio or fallback).

If an asset is missing or send fails:

- Exactly **one** fallback helper in `game_texts` (or `telegram_bot/game_texts.py`), invoked by the adapter — **not** ad-hoc strings in handlers.

---

## 6D — Production Telegram mode

- **Production = single-instance polling** under **systemd** (one process owns `getUpdates`).
- Document in `docs/ops/` or `docs/telegram-local-run.md`: failure modes (two instances), restart, logging.
- **Webhook** explicitly **later**, after HTTPS edge is stable.

---

## 6E — Observability

Add or reuse **low-cardinality** Prometheus series (extend `src/casino_bot/core/metrics.py`):

| Metric | Labels / notes |
|--------|----------------|
| Game rejections | Prefer extending existing `casino_bot_game_round_rejected_total` with `code=access_tokens_required` **or** a dedicated counter — **one canonical series** for pre-round policy rejects. |
| `casino_bot_audio_delivery_total` | `channel` = `telegram`, `cue_type` = `anticipation` \| `win` \| `lose`, `status` = `sent` \| `fallback` \| `failed` |

Record audio metrics in the Telegram adapter after each send attempt.

---

## Acceptance criteria (Phase 6 complete)

- Balance gate at `GAME_ACCESS_MIN_TOKENS` enforced in the **shared** game entry path; reject code `access_tokens_required`; user copy from `game_texts` only.
- No daily debit or `charge_daily_access` in codebase or docs for this phase.
- Telegram `/flip` and `/wheel` consume universal presentation + bot actions where refactored.
- `/wheel` three-step audio/text flow or single fallback from `game_texts`.
- Prod strategy documented: systemd + single polling instance.
- Metrics for `access_tokens_required` (or equivalent) and audio delivery visible on `/metrics`.

---

## Implementation order (suggested)

1. `GAME_ACCESS_MIN_TOKENS` + gate + `access_tokens_required` + tests (new rounds only; before cooldown and stake for those rounds).
2. `GameCommandResult` / `GamePresentation` / `AudioCue` / `BotAction` + Telegram adapter refactor.
3. Token package price constants in settings + `.env.example` / product docs (checkout wiring can follow).
4. Audio assets + fallback consolidation.
5. Metrics + short ops notes / Grafana tweaks if needed.
