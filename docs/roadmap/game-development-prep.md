# Game development preparation roadmap (pre-catalog)

This document defines the minimum product + technical groundwork required before implementing a game catalog and adding multiple games to `casino_bot`.

Scope: **ops-first / production-first**. No new business features unrelated to games.

## Goals

- Ship the **first game** as a safe, observable, auditable vertical slice.
- Avoid **infrastructure completionism**: build only what is required to run games in production.
- Keep the system **non-cash-out** by design until legal + product decisions explicitly change it.

## Non-goals

- A “big catalog” UI before one stable game exists in production.
- Complex provably-fair cryptography before the legal/product brief is finalized.
- Supporting cash-out, token-to-money exchange, or user-to-user transfers (unless legal scope changes).

## Phase 0 — Legal + product brief (blocks game design)

**Exit criteria (DoD):**

- Written legal/product brief answering:
  - Jurisdiction(s), target audience (18+), and distribution channels.
  - Whether the planned mechanics are treated as gambling/lottery/competition/etc.
  - How tokens may be purchased/consumed, and what constitutes a “prize”.
  - Marketing constraints and required user-facing disclosures.
- User onboarding flow includes explicit **18+ confirmation** and acceptance of Terms/Privacy.
- Terms draft exists in repo (initially RU), to be translated to EN later:
  - `docs/legal/terms-of-service-ru.md`

## Phase 1 — Data contract for rounds (the “ledger”)

Before adding a game catalog, the system must be able to record a round in a way that is:
**idempotent**, **auditable**, and **transactionally consistent** with token balance changes.

**Exit criteria (DoD):**

- A minimal “round” record exists (DB schema + migrations), capturing at least:
  - `user_id`, `game_id`, `round_id` (UUID), timestamps
  - bet amount (tokens), result, payout delta (tokens)
  - an idempotency key / request identifier
  - structured details for debugging (without secrets)
- Token debit/credit is performed atomically with round record creation (single transaction).
- Duplicate submissions do not double-spend tokens (idempotency enforced).

## Phase 2 — Game engine interface (one vertical slice)

Define a single entrypoint for game execution so multiple games can share:
limits, idempotency, audit, metrics, and error handling.

**Exit criteria (DoD):**

- A game interface exists (conceptually):
  - Input: `user_id`, bet, idempotency key, optional “client context”
  - Output: outcome + token delta + prize payload (e.g., “win music” identifier)
- One minimal game is implemented end-to-end (“vertical slice”), e.g.:
  - coin flip / simple wheel / minimal slots
- A single config surface exists for tuning (min/max bet, cooldowns), without redeploy for small changes.

## Phase 3 — Telegram UX (surface, not logic)

Implement a stable user flow for exactly one game.

**Exit criteria (DoD):**

- Clear flow:
  - choose game → confirm bet → execute → show result → show balance
- User-facing errors are safe and actionable:
  - insufficient tokens, rate limit, temporary failure
- Any “prize” content (e.g., music) is delivered in a non-blocking way (best-effort).

## Phase 4 — Observability + guardrails for games

Games must ship with production-grade visibility from day 1.

**Exit criteria (DoD):**

- Metrics include (at minimum): rounds, bet volume (tokens), payout volume (tokens), errors, latency.
- Rate limiting is applied for game execution per user (and optionally per IP at the proxy layer).
- Alerts exist for:
  - error spikes
  - unusual execution volume
  - unusual payout/bet ratio (sanity guardrail)

## Phase 5 — Game catalog (after one stable game in production)

Only after one game runs reliably under real usage should the catalog expand.

**Exit criteria (DoD):**

- Game registry exists (multiple game handlers behind a stable interface).
- Catalog UI/commands list only games enabled by configuration.
- Second game added with a different mechanic class (proves extensibility).

## Common failure modes (what to avoid)

- Building a “catalog” before the first game is stable under real traffic.
- Mixing legal uncertainty with core game mechanics (forces rewrites).
- Implementing payout logic without idempotency + transactional guarantees.
- Treating observability as optional (“we’ll add metrics later”).

