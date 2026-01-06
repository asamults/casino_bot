from sqlalchemy.orm import Session

from casino_bot.compliance.constraints import (
    forbid_negative_balance,
)
from casino_bot.db.models import TokenAccount, LedgerEntry


def apply_token_delta(
    db: Session,
    account: TokenAccount,
    delta: int,
    reason: str,
) -> None:
    forbid_negative_balance(account.balance, delta)

    account.balance += delta

    entry = LedgerEntry(
        user_id=account.user_id,
        delta=delta,
        reason=reason,
    )
    db.add(entry)
