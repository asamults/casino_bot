## Legal/Product Brief (Phase 0) — UK — casino_bot

**Version:** 0.1  
**Date:** 2026-05-11  
**Owner:** Product (UK, sole trader / self-employed)  
**Scope:** Phase 0 only — written brief to unblock Phase 1–2 engineering (round model, idempotency, first playable prototype) without rework.

---

### 1) Product summary (what we are building)

- **Channel**: Telegram bot.
- **Audience**: **18+ only**.
- **Economy**:
  - Users may receive and spend **tokens** inside the product.
  - Tokens are intended to be used for “stakes” (spend-to-play actions) and may be **debited per action** and/or **debited daily** depending on the chosen mechanic.
  - Tokens may be **credited** on “win”.
- **Outcomes / “prizes”**:
  - Non-cash “prize” may include **music / sound playback**.
  - Product may also award **tokens**.
- **Cash-out**: **No cash-out, no withdrawal, no fiat prizes, no token-to-money redemption**. Not planned until a separate legal decision.

---

### 2) Jurisdiction & geo scope (explicit Phase 0 decision)

**Phase 1–2 engineering must assume the product is UK-only in any real-money context.**

- **Jurisdiction for legal opinion**: United Kingdom (England & Wales as default unless the operator is in Scotland/NI).
- **Users served (Phase 1–2)**:
  - **Allowed**: UK residents only (pilot / closed beta).
  - **Not served / hard blocked** until additional legal review and localized documents: **US (all states), Canada, Australia, Belgium, Netherlands, and any other jurisdiction where the legal opinion indicates additional licensing requirements or higher enforcement risk.**
- **Implementation requirement**: add a **geo restriction control** (at minimum: self-declared country + IP-based risk flag) before enabling any monetization. (Engineering detail can wait; requirement is to not ship monetization globally.)

---

### 3) Regulatory classification — required legal conclusion (must be answered by UK counsel)

**UK counsel must provide a written classification under the Gambling Act 2005 and related UK rules**, with reasoning and a “go / no-go” for a monetized version of the mechanics.

Counsel must explicitly conclude whether the product (as monetized) is best classified as:

- **Gambling** (gaming / betting / lottery) and whether it is **remote gambling** requiring licensing; OR
- **Prize competition** / **free draw** (and under which conditions); OR
- **Digital entertainment / subscription** with virtual credits; OR
- Any other applicable category.

This is a gating output: Phase 1–2 can proceed only with the **non-monetized prototype** path (see Section 9), while Phase 3+ monetization depends on counsel’s conclusion.

---

### 4) Consideration (what counts as “pay to participate”) — required legal conclusion

Counsel must explicitly analyze whether the following are “consideration” for the purposes of UK gambling definitions and consumer law:

- **Purchase of tokens** for money.
- **Subscription fee** that grants access to play and/or periodic token allowances.
- **Daily token debit** (even if tokens were initially purchased) as an ongoing “cost of participation”.
- Any **indirect consideration**, including time-limited offers or bundles that effectively require payment to meaningfully participate.

**Phase 0 decision for Phase 1–2**: no feature may create consideration in production:

- No paid subscription.
- No token purchases.
- No paid bundles.
- Tokens used in Phase 1–2 are **non-purchased test/play tokens only**.

---

### 5) Prize analysis (“money or money’s worth”) — required legal conclusion

Counsel must explicitly analyze whether:

- **Tokens** are or could be viewed as “money’s worth” (e.g., if transferable, tradable, giftable, or usable in a way that has external value).
- **Music / sound playback** could be considered a prize of value.

**Phase 0 decisions (hard constraints in product design until further legal step):**

- Tokens are **non-transferable**, **non-withdrawable**, **non-redeemable**, **no secondary market**, **no gifting**, **no P2P**, **no marketplace**.
- Any “prize” is **digital entertainment only** (e.g., audio playback, cosmetic/UX effects) and **cannot be exchanged** for money or items of external value.

---

### 6) Marketing / branding restrictions (explicit Phase 0 decision)

Until UK counsel explicitly clears the marketing language, **avoid gambling-adjacent branding**.

- **Do not use** in UK marketing materials, bot name, or UI text: “casino”, “bet”, “wager”, “stake”, “win money”, “cash”, “jackpot”, “prize money”.
- Prefer neutral terms: “game”, “play”, “round”, “reward”, “points”, “credits”, “entertainment”.

Project repository name can remain, but **public-facing** naming must follow the above.

---

### 7) Age / identity verification (18+)

Counsel must advise what is sufficient for “18+ only” in the UK in this context, including:

- Whether **self-attestation** (checkbox/button) is acceptable for a free prototype.
- What threshold is required if monetization is introduced (e.g., age estimation, document checks, or payment-instrument-based checks), and whether any third-party age verification is recommended.

**Phase 0 decision for Phase 1–2**:

- Implement **explicit 18+ confirmation** on first run.
- Block use if user declines.
- Store an audit flag (timestamp + version of ToS/Privacy accepted). No ID document collection in Phase 1–2.

---

### 8) Consumer law, refunds, and cancellation

Counsel must provide written guidance for:

- Refund rights and cancellation for any subscription or token purchases (if later introduced).
- Required pre-contract information and “digital content” rules.
- Payment provider policies that must be reflected in the UI and docs.

**Phase 0 decision for Phase 1–2**: no paid features, therefore no refund flows in Phase 1–2 scope.

---

### 9) Allowed vs forbidden mechanics (Phase 0 decisions)

**Allowed for Phase 1–2 prototype (no real money):**

- RNG / pseudo-RNG for entertainment outcomes.
- Tables of outcomes / probability tuning (internal).
- Token debits per action / daily debits **only using non-purchased tokens**.
- Token credits on “win” **only using non-purchased tokens**.
- “Lootbox-like” reveals **only** if no paid entry and prizes have no external value.

**Forbidden until a separate legal step (hard “do not build”):**

- Cash-out / withdrawal / redemption.
- P2P transfers, gifting, tipping, or any user-to-user token movement.
- Marketplace / secondary market / trading.
- Any feature that enables users to obtain **external value** from tokens or prizes.
- Any mechanism that allows participation conditioned on payment (subscription or token purchase) **unless and until counsel clears the design**.

---

### 10) Engineering constraints to prevent rework (what Phase 1–2 should assume)

To keep Phase 1–2 reusable regardless of counsel’s outcome:

- **Ledger separation**: architect tokens as a **strict internal ledger** with a “source” dimension:
  - `test_grant` (allowed now)
  - `promo_grant` (future)
  - `purchased` (future — must be gated behind legal decision)
- **Feature flags**: monetization-related features must be behind flags defaulting **OFF**.
- **No user-to-user value flows**: keep the economy strictly single-user.
- **Auditability**: acceptance records for 18+ + ToS + Privacy must be stored.

---

### 11) Open items that are NOT allowed to remain open (Phase 0 must close)

This brief is considered “done” only when UK counsel provides written answers for:

- Final classification (gambling / lottery / prize competition / subscription entertainment / etc.).
- Whether token purchase, token staking, RNG outcome, and token winnings are compatible in a monetized product in the UK.
- Whether tokens can be “money’s worth” under the proposed restrictions.
- Whether “casino” branding is acceptable in UK marketing (expected: **no** until cleared).
- Required age verification level for:
  - free prototype
  - monetized product

