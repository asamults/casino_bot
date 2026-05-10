"""DB helpers for the Telegram adapter (sync; used from async handlers via threads)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from casino_bot.db.models import TokenAccount, User
from casino_bot.services import economy_service
from casino_bot.telegram_bot.texts import BALANCE_UNAVAILABLE, format_balance_message

_TELEGRAM_ACTOR = "telegram_bot"


def get_user_by_telegram_id(db: Session, telegram_user_id: int) -> User | None:
    return db.query(User).filter(User.telegram_user_id == telegram_user_id).first()


def ensure_telegram_user(db: Session, *, telegram_user_id: int) -> User:
    """Return existing row or create ``User`` (and empty token wallet) atomically."""
    user = get_user_by_telegram_id(db, telegram_user_id)
    if user is not None:
        return user
    return economy_service.create_user(
        db,
        actor=_TELEGRAM_ACTOR,
        telegram_user_id=telegram_user_id,
    )


def resolve_balance_reply(db: Session, *, user_id: int) -> str:
    """Return a balance line or a safe unavailable message (never raises)."""
    acc = db.query(TokenAccount).filter(TokenAccount.user_id == user_id).first()
    if acc is None:
        return BALANCE_UNAVAILABLE
    return format_balance_message(acc.balance)
