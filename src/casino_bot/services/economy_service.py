"""Token ledger adjustments (integer token_units, Phase 7)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from casino_bot.compliance.context import ComplianceContext
from casino_bot.compliance.registry import Operation, validate_operation
from casino_bot.db.models import LedgerEntry, TokenAccount, User
from casino_bot.services import token_amounts
from casino_bot.services.audit_service import audit_log


def create_user(
    db: Session,
    *,
    actor: str,
    internal_note: str | None = None,
    telegram_user_id: int | None = None,
    whatsapp_phone_e164: str | None = None,
    billing_customer_id: str | None = None,
) -> User:
    """Create a ``User`` and empty ``TokenAccount``; flush only (caller commits)."""
    user = User(
        is_active=True,
        internal_note=internal_note,
        telegram_user_id=telegram_user_id,
        whatsapp_phone_e164=whatsapp_phone_e164,
        billing_customer_id=billing_customer_id,
    )
    db.add(user)
    db.flush()
    db.add(TokenAccount(user_id=user.id, balance=0.0, balance_units=0))
    audit_log(
        db,
        actor=actor,
        action="user_created",
        details={
            "user_id": user.id,
            "telegram_user_id": telegram_user_id,
            "whatsapp_phone_e164": whatsapp_phone_e164,
        },
    )
    return user


def adjust_user_tokens(
    db: Session,
    *,
    user_id: int,
    delta_units: int,
    reason: str,
    actor: str,
    pending_transfer: bool = False,
    pending_cash_out: bool = False,
) -> TokenAccount:
    """Apply ``delta_units`` to the user's token account after compliance checks.

    Runs validators before mutating ``balance_units``, writes a ledger row and audit
    entry. Does not commit; caller should ``commit`` or ``rollback``.
    """
    from casino_bot.settings import settings as app_settings

    scale = app_settings.TOKEN_UNIT_SCALE
    token_amounts.validate_units(delta_units, name="delta_units")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise ValueError("User not found")

    # Test sessions (and some callers) may run with autoflush disabled; ensure
    # pending inserts (e.g. TokenAccount created alongside User) are visible to
    # subsequent SELECTs and we don't create duplicate token accounts.
    db.flush()

    q = db.query(TokenAccount).filter(TokenAccount.user_id == user_id)
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        q = q.with_for_update()
    account = q.first()
    if account is None:
        account = TokenAccount(user_id=user_id, balance=0.0, balance_units=0)
        db.add(account)
        db.flush()

    operation = Operation.TOKEN_CREDIT if delta_units >= 0 else Operation.TOKEN_DEBIT
    ctx = ComplianceContext(
        balance_units=account.balance_units,
        delta_units=delta_units,
        pending_transfer=pending_transfer,
        pending_cash_out=pending_cash_out,
    )
    validate_operation(operation, ctx)

    account.balance_units += delta_units
    account.balance = token_amounts.units_to_storage_float(
        account.balance_units, scale=scale
    )
    db.add(
        LedgerEntry(
            user_id=user_id,
            delta=token_amounts.units_to_storage_float(delta_units, scale=scale),
            delta_units=delta_units,
            reason=reason,
        )
    )
    audit_log(
        db,
        actor=actor,
        action="token_balance_adjust",
        details={
            "user_id": user_id,
            "delta_units": delta_units,
            "reason": reason,
            "balance_units_after": account.balance_units,
        },
    )
    return account
