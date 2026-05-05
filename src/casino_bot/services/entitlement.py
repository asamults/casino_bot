"""Subscription entitlement checks (no payment SDK)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from casino_bot.db.models import Subscription
from casino_bot.settings import settings

SUBSCRIPTION_STATUS_ACTIVE = "active"
ENTITLEMENT_REQUIRED_CODE = "ENTITLEMENT_REQUIRED"


def user_has_active_subscription(db: Session, user_id: int) -> bool:
    """Return whether ``user_id`` has an active subscription for gating features.

    Current logic: a row with ``status == 'active'`` and, if ``current_period_end``
    is set, it must be in the future. When Stripe/Paddle (or similar) is wired in,
    webhook handlers should upsert ``subscriptions`` and refresh ``status`` and
    ``current_period_end``; this function remains the single read-side gate.
    """
    now = datetime.now(UTC)
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status == SUBSCRIPTION_STATUS_ACTIVE,
        )
        .first()
    )
    if sub is None:
        return False
    if sub.current_period_end is None:
        return True
    grace = timedelta(seconds=max(0, settings.ENTITLEMENT_GRACE_SECONDS))
    return sub.current_period_end + grace > now


def require_active_entitlement(db: Session, *, user_id: int) -> None:
    if user_has_active_subscription(db, user_id):
        return
    if settings.ENTITLEMENT_ENFORCEMENT_MODE == "soft":
        return
    raise HTTPException(
        status_code=402,
        detail={
            "code": ENTITLEMENT_REQUIRED_CODE,
            "message": "Active subscription required",
        },
    )
