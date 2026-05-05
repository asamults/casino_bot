"""Paginated user catalog and detail reads."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from casino_bot.db.models import User


def list_users(
    db: Session,
    *,
    skip: int,
    limit: int,
    is_active: bool | None = None,
    telegram_user_id: int | None = None,
    whatsapp_contains: str | None = None,
) -> tuple[list[User], int]:
    q = db.query(User)
    if is_active is not None:
        q = q.filter(User.is_active == is_active)
    if telegram_user_id is not None:
        q = q.filter(User.telegram_user_id == telegram_user_id)
    if whatsapp_contains:
        term = f"%{whatsapp_contains.strip()}%"
        q = q.filter(User.whatsapp_phone_e164.ilike(term))
    total = q.count()
    items = q.order_by(User.id.desc()).offset(skip).limit(limit).all()
    return items, total


def get_user_detail(db: Session, user_id: int) -> User | None:
    return (
        db.query(User)
        .options(
            joinedload(User.token_account),
            joinedload(User.subscriptions),
        )
        .filter(User.id == user_id)
        .first()
    )
