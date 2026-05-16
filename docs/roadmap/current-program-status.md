# Current program status

Last updated for baseline: **`main` = `origin/main`**, HEAD **`8ee9503`**, tag **`phase7-token-units-accounting-green-2026-05-15`** (Phase 7 PR #24 merged). Working tree expected clean after release.

## Phase closure table

| Phase | Scope | Code/docs in repo | Operational proof |
|-------|--------|-------------------|-------------------|
| 4 | Metrics, guardrails, Grafana | Closed | Use prod traffic to tune |
| 5 | Game catalog, `bonus_wheel` | Closed | — |
| 6 | Balance gate, `access_tokens_required` | Closed (`phase6-balance-access-green-2026-05-14`) | — |
| 6D | systemd unit, runbook, smoke, prod env examples | **Closed** (`phase6d-prod-telegram-polling-green-2026-05-14`, PR #23) | **VPS rehearsal** — see below |
| 7 | Integer `token_units`, `TOKEN_UNIT_SCALE=1000` | **Closed** (PR #24, tag above) | Run migrations on each environment |

### Phase 6D: two layers (important)

| Layer | Meaning | Status |
|-------|---------|--------|
| **6D implementation** | Unit file, runbook, smoke script, tests, env examples | **Done** |
| **6D VPS rehearsal** | Real host: `systemctl`, `/etc/casino-bot/telegram.env`, one poller, manual Telegram checks | **Pending** until executed on production VPS |

Having a tag on `main` does **not** replace proving runtime on the server.

## Engineering boundary crossed (Phase 7)

Money-adjacent token accounting should use **integer `token_units`** only in active paths. Checkout and real customer payments must **not** be built on float balances.

Legacy float columns (if any remain) are **compatibility mirrors only** until removed in a follow-up migration — not source of truth.

## Maturity snapshot (subjective)

| Area | Score | Notes |
|------|-------|--------|
| Game + ledger architecture | **8/10** | Idempotent rounds, units, compliance, adapter separation |
| Telegram runtime readiness | **6.5/10** before VPS rehearsal; **~8/10** after | Artifacts exist; prove on VPS |
| Payment readiness | **6/10** | Billing skeleton; package checkout not closed |
| Prod / business readiness | **5.5–6/10** | Legal/product contract + prod API surface still in flight |

**Strengths:** round idempotency, integer units, ledger as source of truth, metrics, systemd/runbook, no entitlement in game path, no daily debit model.

**Gaps:** VPS rehearsal, Phase 7.5 contract in README, Phase 8 checkout design → implementation, webhook crediting tied to `delta_units`, prod API (HTTPS, backups, billing webhooks), explicit legal framing for tokens/games.

## North star (strict order)

```text
Phase 7 closed (main @ 8ee9503)
→ Step 1: VPS polling rehearsal (6D operational proof)
→ Step 2: Phase 7.5 product / legal / runtime contract (short, authoritative)
→ Step 3: Phase 8 checkout design doc (no code yet)
→ Step 4: Phase 8 checkout implementation (integer units via economy_service only)
→ Step 5: Prod API / webhook / HTTPS / backups hardening
```

**Hard rules until Phase 8 implementation is reviewed:**

- No checkout code before **Phase 8 design** is written and agreed.
- No real customer payments before **Phase 7** is deployed on the target DB and **Phase 7.5** contract is visible to operators.
- Do not reintroduce float as source of truth for balances or ledger.

## What to do next (pick one track)

| Priority | Work | Doc |
|----------|------|-----|
| 1 | VPS 6D rehearsal | `phase6d-vps-rehearsal-checklist.md` |
| 2 | Contract cleanup (README pointer + legal note) | `phase7.5-product-runtime-contract.md` |
| 3 | Checkout design | `phase8-token-package-checkout.md` |
| 4 | Checkout implementation | After design sign-off |
| 5 | Prod API for webhooks | `../ops/deployment-contract.md`, cutover checklists |

## Tags (reference)

- `phase4-game-observability-green-2026-05-12`
- `phase5-game-catalog-green-2026-05-12`
- `phase6-balance-access-green-2026-05-14`
- `phase6d-prod-telegram-polling-green-2026-05-14`
- `phase7-token-units-accounting-green-2026-05-15`
