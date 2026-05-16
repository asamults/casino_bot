# Phase 8 — Token package checkout (design)

Status: **design only** — **no implementation** until this document is reviewed and Phase 7.5 contract is aligned.

**Prerequisites:**

- Phase 7 merged and migrated on target environments (`balance_units`, `delta_units`).
- Phase 7.5 contract accepted (`phase7.5-product-runtime-contract.md`).
- VPS polling rehearsal done or scheduled (`phase6d-vps-rehearsal-checklist.md`).

**Non-goals:** new billing provider; new games; cash-out; changing game access rules.

---

## Packages (canonical)

| `package_id` (example) | GBP | Visible tokens | `token_units` credit (`SCALE=1000`) |
|------------------------|-----|----------------|-------------------------------------|
| `pack_100` | 1 | 100 | `100_000` |
| `pack_1000` | 5 | 1_000 | `1_000_000` |
| `pack_10000` | 20 | 10_000 | `10_000_000` |

Settings may expose `TOKEN_PACKAGE_*_PRICE_GBP` for copy; **credit amount is always fixed integer units**, not derived from float.

---

## End-to-end flow

```text
User initiates checkout (Telegram link / web / admin-assisted)
  → Provider checkout session (Stripe or Paddle — existing adapters)
  → User pays in GBP
  → Provider webhook → casino_bot billing API
  → Verify signature + event type + idempotency
  → Resolve package_id → delta_units (fixed table)
  → economy_service.adjust_user_tokens(delta_units=..., reason=..., actor=billing_webhook)
  → ledger_entries.delta_units + token_accounts.balance_units + audit
  → User can play if balance_units meets GAME_ACCESS_MIN_TOKENS * SCALE
```

---

## Hard rules

1. **Webhook handlers must not** update `balance_units` directly.
2. **All** credits go through **`economy_service`** (compliance + ledger + audit).
3. **Idempotency:** duplicate webhook / retry must **not** double-credit (provider event id + internal idempotency key — align with existing `billing_webhook_events` patterns).
4. **Failed / cancelled / unpaid** events → **no** credit.
5. **Partial / ambiguous** events → no credit until explicitly mapped; log + metric.
6. **Integer only:** `delta_units` from package table; reject non-integer or unknown package.

---

## Idempotency and audit

| Concern | Approach |
|---------|----------|
| Provider event id | Store in `billing_webhook_events` (or extend); unique per provider |
| Credit once | Before `adjust_user_tokens`, check event already processed |
| Audit | `audit_log` with `package_id`, `delta_units`, `external_event_id` (no card data) |
| Metrics | Extend existing webhook counters; optional `token_package_credited_total{package_id}` — low cardinality |

---

## User-facing surfaces (minimal)

- Link from `/balance` or `/help`: “Buy tokens” → checkout URL (return URL allowlist per existing billing settings).
- After success, user sees updated balance (display in visible tokens).

No promise of monetary winnings; align copy with Phase 7.5.

---

## Failure modes

| Case | Behavior |
|------|----------|
| Duplicate webhook | 200/ack per provider contract; **no** second credit |
| Invalid signature | Reject; no credit |
| Unknown package | No credit; alert/log |
| DB down | Retry per provider; idempotency prevents double credit on recovery |

---

## Testing (implementation phase)

- Webhook fixture: paid → exact `delta_units` once.
- Duplicate delivery → single credit.
- Failed payment → balance unchanged.
- Ledger sum invariant vs `balance_units` after credit.

---

## Prod API dependencies (Step 5)

Checkout webhooks require a **stable HTTPS** endpoint, secrets on host, and backups. Coordinate with `docs/ops/deployment-contract.md` and production cutover checklists.

---

## Implementation prompt (after design sign-off)

When ready, open branch `phase8-token-package-checkout` from `main` and implement only what this design specifies; run `ruff`, `pytest`, env contract validation. Do not change `TOKEN_UNIT_SCALE` or game access gate semantics without updating Phase 7.5 doc.
