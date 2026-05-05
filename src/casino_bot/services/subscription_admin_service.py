"""Subscription reads and manual (internal) activation for testing — no external billing SDK."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from casino_bot.db.models import Subscription
from casino_bot.services.audit_service import audit_log
from casino_bot.services.entitlement import SUBSCRIPTION_STATUS_ACTIVE


def get_subscriptions_for_user(db: Session, user_id: int) -> list[Subscription]:
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.id.desc())
        .all()
    )


def activate_internal_test_plan(
    db: Session,
    *,
    user_id: int,
    plan_code: str,
    actor_email: str,
    period_days: int = 30,
) -> Subscription:
    """Create or refresh an active subscription row for entitlement testing.

    Sets ``provider`` to ``internal``. Real billing webhooks (e.g. Stripe) would
    upsert rows with provider-specific IDs later; this path is for QA only.
    """
    now = datetime.now(UTC)
    end = now + timedelta(days=period_days)
    existing = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.plan_code == plan_code,
        )
        .first()
    )
    if existing:
        existing.provider = "internal"
        existing.status = SUBSCRIPTION_STATUS_ACTIVE
        existing.current_period_end = end
        existing.external_subscription_id = None
        existing.provider_customer_id = None
        existing.provider_subscription_id = None
        existing.cancel_at_period_end = False
        existing.entitlement_active = True
        existing.updated_at = now
        sub = existing
    else:
        sub = Subscription(
            user_id=user_id,
            provider="internal",
            external_subscription_id=None,
            provider_customer_id=None,
            provider_subscription_id=None,
            status=SUBSCRIPTION_STATUS_ACTIVE,
            plan_code=plan_code,
            current_period_end=end,
            cancel_at_period_end=False,
            entitlement_active=True,
        )
        db.add(sub)
        db.flush()
    audit_log(
        db,
        actor=actor_email,
        action="subscription_internal_activate",
        details={
            "user_id": user_id,
            "plan_code": plan_code,
            "subscription_id": sub.id,
            "period_days": period_days,
        },
    )
    return sub


def deactivate_internal_test_plan(
    db: Session,
    *,
    user_id: int,
    actor_email: str,
) -> int:
    rows = db.query(Subscription).filter(Subscription.user_id == user_id).all()
    now = datetime.now(UTC)
    count = 0
    for sub in rows:
        sub.status = "canceled"
        sub.cancel_at_period_end = True
        sub.entitlement_active = False
        sub.current_period_end = now
        sub.updated_at = now
        count += 1
    audit_log(
        db,
        actor=actor_email,
        action="subscription_internal_deactivate",
        details={"user_id": user_id, "affected_subscriptions": count},
    )
    return count


def link_test_subscription(
    db: Session,
    *,
    user_id: int,
    actor_email: str,
    provider: str,
    provider_customer_id: str | None,
    provider_subscription_id: str | None,
    plan_code: str,
    status: str,
) -> Subscription:
    now = datetime.now(UTC)
    row = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.provider == provider,
        )
        .first()
    )
    if row is None:
        row = Subscription(
            user_id=user_id,
            provider=provider,
            status=status,
            plan_code=plan_code,
        )
        db.add(row)
    row.provider_customer_id = provider_customer_id
    row.provider_subscription_id = provider_subscription_id
    row.external_subscription_id = provider_subscription_id
    row.status = status
    row.plan_code = plan_code
    row.cancel_at_period_end = False
    row.entitlement_active = status in {"active", "trialing"}
    row.updated_at = now
    db.flush()
    audit_log(
        db,
        actor=actor_email,
        action="subscription_link_test",
        details={
            "user_id": user_id,
            "provider": provider,
            "subscription_id": row.id,
        },
    )
    return row
