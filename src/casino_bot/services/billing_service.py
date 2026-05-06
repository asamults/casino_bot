from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from casino_bot.billing.providers import PROVIDER_ADAPTERS, get_primary_provider_adapter
from casino_bot.billing.providers.base import (
    NormalizedBillingEvent,
    NotImplementedForProvider,
)
from casino_bot.db.models import BillingWebhookEvent, Subscription, User
from casino_bot.core.pii import mask_token_like
from casino_bot.services.audit_service import audit_log
from casino_bot.settings import settings
from casino_bot.core.security import utcnow

ENTITLEMENT_ACTIVE_STATUSES = {"active", "trialing"}


def create_webhook_event(
    db: Session, *, event: NormalizedBillingEvent, raw_body: bytes
) -> BillingWebhookEvent | None:
    row = BillingWebhookEvent(
        provider=event.provider,
        external_event_id=event.external_event_id,
        event_type=event.event_type,
        payload_hash=hashlib.sha256(raw_body).hexdigest(),
        status="received",
        raw_payload=event.raw,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return None
    return row


def process_normalized_event(
    db: Session, *, event_row: BillingWebhookEvent, event: NormalizedBillingEvent
) -> str:
    event_row.attempts_count += 1
    event_row.last_attempt_at = utcnow()
    event_row.last_error_code = None
    event_row.last_error_message = None
    if not event.external_event_id:
        event_row.status = "ignored"
        event_row.error_message = "Missing external_event_id"
        event_row.last_error_code = "missing_external_event_id"
        event_row.last_error_message = "Missing external_event_id"
        event_row.processed_at = utcnow()
        db.flush()
        return "ignored"

    if event.status is None and event.event_type:
        event_row.status = "ignored"
        event_row.error_message = "Unsupported event type"
        event_row.last_error_code = "unsupported_event"
        event_row.last_error_message = "Unsupported event type"
        event_row.processed_at = utcnow()
        db.flush()
        return "ignored"

    user = _resolve_user(db, event)
    if user is None:
        event_row.status = "failed"
        event_row.error_message = "Unable to map event to user"
        event_row.last_error_code = "mapping_failed"
        event_row.last_error_message = "Unable to map event to user"
        event_row.processed_at = utcnow()
        if event_row.attempts_count >= settings.BILLING_DEAD_LETTER_ATTEMPTS:
            event_row.dead_letter = True
        audit_log(
            db,
            actor="billing-webhook",
            action="billing_mapping_failed",
            details={
                "provider": event.provider,
                "external_event_id": event.external_event_id,
            },
        )
        db.flush()
        return "failed"

    sub = _upsert_subscription(db, event=event, user_id=user.id)
    event_row.status = "processed"
    event_row.processed_at = utcnow()
    audit_log(
        db,
        actor="billing-webhook",
        action="billing_subscription_synced",
        details={
            "provider": event.provider,
            "external_event_id": event.external_event_id,
            "subscription_id": sub.id,
            "user_id": user.id,
            "status": sub.status,
            "entitlement_active": sub.entitlement_active,
        },
    )
    db.flush()
    return "processed"


def _resolve_user(db: Session, event: NormalizedBillingEvent) -> User | None:
    if event.user_hint is not None:
        by_hint = db.query(User).filter(User.id == event.user_hint).first()
        if by_hint:
            return by_hint
    if event.customer_id:
        by_customer = (
            db.query(User).filter(User.billing_customer_id == event.customer_id).first()
        )
        if by_customer:
            return by_customer
    return None


def _upsert_subscription(
    db: Session, *, event: NormalizedBillingEvent, user_id: int
) -> Subscription:
    sub = None
    if event.subscription_id:
        sub = (
            db.query(Subscription)
            .filter(
                Subscription.provider == event.provider,
                Subscription.provider_subscription_id == event.subscription_id,
            )
            .first()
        )
    if sub is None and event.customer_id:
        sub = (
            db.query(Subscription)
            .filter(
                Subscription.user_id == user_id,
                Subscription.provider == event.provider,
                Subscription.provider_customer_id == event.customer_id,
            )
            .first()
        )
    if sub is None:
        sub = Subscription(
            user_id=user_id,
            provider=event.provider,
            plan_code=event.plan_code or "unknown_plan",
            status=event.status or "unknown",
        )
        db.add(sub)

    sub.user_id = user_id
    sub.provider = event.provider
    sub.provider_customer_id = event.customer_id
    sub.provider_subscription_id = event.subscription_id
    sub.external_subscription_id = event.subscription_id
    sub.status = event.status or "unknown"
    sub.plan_code = event.plan_code or sub.plan_code
    sub.current_period_end = event.current_period_end
    sub.cancel_at_period_end = event.cancel_at_period_end
    sub.entitlement_active = _is_entitlement_active(sub.status, sub.current_period_end)
    sub.updated_at = utcnow()
    db.flush()
    return sub


def _is_entitlement_active(status: str | None, period_end) -> bool:
    if status not in ENTITLEMENT_ACTIVE_STATUSES:
        return False
    if period_end is None:
        return True
    grace = timedelta(seconds=max(0, settings.ENTITLEMENT_GRACE_SECONDS))
    return period_end + grace > utcnow()


def list_billing_events(
    db: Session,
    *,
    provider: str | None,
    status: str | None,
    dead_letter: bool | None,
    skip: int,
    limit: int,
) -> tuple[list[BillingWebhookEvent], int]:
    q = db.query(BillingWebhookEvent)
    if provider:
        q = q.filter(BillingWebhookEvent.provider == provider)
    if status:
        q = q.filter(BillingWebhookEvent.status == status)
    if dead_letter is not None:
        q = q.filter(BillingWebhookEvent.dead_letter == dead_letter)
    total = q.count()
    rows = q.order_by(BillingWebhookEvent.id.desc()).offset(skip).limit(limit).all()
    return rows, total


def safe_process_webhook(
    db: Session, *, event_row: BillingWebhookEvent, event: NormalizedBillingEvent
) -> str:
    try:
        status = process_normalized_event(db, event_row=event_row, event=event)
        db.commit()
        return status
    except HTTPException:
        raise
    except Exception as exc:
        event_row.attempts_count += 1
        event_row.error_message = "processing_error"
        event_row.last_attempt_at = utcnow()
        event_row.last_error_code = "processing_error"
        event_row.last_error_message = "processing_error"
        if event_row.attempts_count >= settings.BILLING_DEAD_LETTER_ATTEMPTS:
            event_row.dead_letter = True
        db.commit()
        raise HTTPException(
            status_code=500, detail="Webhook processing failed"
        ) from exc


def _validate_return_url(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if not host or host not in {
        h.lower() for h in settings.BILLING_ALLOWED_RETURN_HOSTS
    }:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_RETURN_URL",
                "message": "Return URL host is not allowed",
            },
        )


def _validate_plan(plan_code: str) -> None:
    if plan_code not in settings.BILLING_ALLOWED_PLANS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PLAN_CODE",
                "message": "Unknown or unsupported plan",
            },
        )


def create_checkout_session(
    db: Session,
    *,
    user_id: int,
    plan_code: str,
    success_url: str,
    cancel_url: str,
) -> dict:
    if not settings.BILLING_ENABLE_CHECKOUT:
        raise HTTPException(
            status_code=503,
            detail={"code": "CHECKOUT_DISABLED", "message": "Checkout is disabled"},
        )
    _validate_plan(plan_code)
    _validate_return_url(success_url)
    _validate_return_url(cancel_url)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    adapter = get_primary_provider_adapter()
    customer_id = adapter.create_or_get_customer(
        user_id=user_id,
        email_hint=None,
        existing_customer_id=user.billing_customer_id,
    )
    user.billing_customer_id = customer_id
    result = adapter.create_checkout_session(
        customer_id=customer_id,
        plan_code=plan_code,
        success_url=success_url,
        cancel_url=cancel_url,
        user_id=user_id,
    )
    audit_log(
        db,
        actor=f"user:{user_id}",
        action="checkout_session_created",
        details={
            "provider": result.provider,
            "plan_code": plan_code,
            "customer_id": mask_token_like(customer_id),
        },
    )
    db.commit()
    return {
        "provider": result.provider,
        "checkout_url": result.checkout_url,
        "session_id": result.session_id,
    }


def get_user_subscription(db: Session, *, user_id: int) -> Subscription | None:
    return (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.updated_at.desc())
        .first()
    )


def request_cancel_subscription(db: Session, *, user_id: int) -> dict:
    sub = get_user_subscription(db, user_id=user_id)
    if sub is None or not sub.provider_subscription_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    adapter = get_primary_provider_adapter()
    try:
        result = adapter.cancel_subscription(
            provider_subscription_id=sub.provider_subscription_id
        )
    except NotImplementedForProvider as exc:
        raise HTTPException(
            status_code=501,
            detail={"code": "PROVIDER_NOT_IMPLEMENTED", "message": str(exc)},
        ) from exc
    sub.cancel_at_period_end = bool(result.get("cancel_at_period_end", True))
    sub.status = adapter.normalize_status(result.get("status"))
    sub.entitlement_active = _is_entitlement_active(sub.status, sub.current_period_end)
    sub.updated_at = utcnow()
    audit_log(
        db,
        actor=f"user:{user_id}",
        action="subscription_cancel_requested",
        details={"subscription_id": sub.id},
    )
    db.commit()
    return {"status": "ok", "cancel_at_period_end": sub.cancel_at_period_end}


def request_resume_subscription(db: Session, *, user_id: int) -> dict:
    sub = get_user_subscription(db, user_id=user_id)
    if sub is None or not sub.provider_subscription_id:
        raise HTTPException(status_code=404, detail="Subscription not found")
    adapter = get_primary_provider_adapter()
    try:
        result = adapter.resume_subscription(
            provider_subscription_id=sub.provider_subscription_id
        )
    except NotImplementedForProvider as exc:
        raise HTTPException(
            status_code=501,
            detail={"code": "PROVIDER_NOT_IMPLEMENTED", "message": str(exc)},
        ) from exc
    sub.cancel_at_period_end = bool(result.get("cancel_at_period_end", False))
    sub.status = adapter.normalize_status(result.get("status"))
    sub.entitlement_active = _is_entitlement_active(sub.status, sub.current_period_end)
    sub.updated_at = utcnow()
    audit_log(
        db,
        actor=f"user:{user_id}",
        action="subscription_resume_requested",
        details={"subscription_id": sub.id},
    )
    db.commit()
    return {"status": "ok", "cancel_at_period_end": sub.cancel_at_period_end}


def create_portal_link(db: Session, *, user_id: int, return_url: str) -> dict:
    if not settings.BILLING_ENABLE_PORTAL:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "PORTAL_DISABLED",
                "message": "Customer portal is disabled",
            },
        )
    _validate_return_url(return_url)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.billing_customer_id:
        raise HTTPException(status_code=404, detail="Billing customer not found")
    adapter = get_primary_provider_adapter()
    try:
        result = adapter.create_portal_session(
            customer_id=user.billing_customer_id, return_url=return_url
        )
    except NotImplementedForProvider as exc:
        raise HTTPException(
            status_code=501,
            detail={"code": "PROVIDER_NOT_IMPLEMENTED", "message": str(exc)},
        ) from exc
    audit_log(
        db,
        actor=f"user:{user_id}",
        action="portal_link_created",
        details={"provider": result.provider},
    )
    db.commit()
    return {"provider": result.provider, "portal_url": result.portal_url}


def replay_webhook_event(db: Session, *, event_id: int) -> dict:
    row = (
        db.query(BillingWebhookEvent).filter(BillingWebhookEvent.id == event_id).first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Billing event not found")
    if not row.raw_payload:
        raise HTTPException(status_code=400, detail="Replay payload unavailable")
    adapter = PROVIDER_ADAPTERS.get(row.provider)
    if adapter is None:
        raise HTTPException(status_code=400, detail="Unknown provider")
    raw_body = json.dumps(row.raw_payload).encode("utf-8")
    event = adapter.parse_event(raw_body)
    status = process_normalized_event(db, event_row=row, event=event)
    row.last_replayed_at = utcnow()
    if row.attempts_count >= settings.BILLING_DEAD_LETTER_ATTEMPTS:
        row.dead_letter = True
    db.commit()
    return {
        "status": status,
        "attempts_count": row.attempts_count,
        "dead_letter": row.dead_letter,
    }


def undelete_dead_letter(db: Session, *, event_id: int) -> dict:
    row = (
        db.query(BillingWebhookEvent).filter(BillingWebhookEvent.id == event_id).first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Billing event not found")
    row.dead_letter = False
    row.last_error_code = None
    row.last_error_message = None
    db.commit()
    return {"status": "ok", "dead_letter": row.dead_letter}


def cleanup_old_webhook_events(db: Session, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=max(0, settings.BILLING_WEBHOOK_RETENTION_DAYS))
    q = db.query(BillingWebhookEvent).filter(
        BillingWebhookEvent.received_at < cutoff,
        BillingWebhookEvent.status.in_(["processed", "ignored", "idempotent"]),
    )
    count = q.count()
    q.delete(synchronize_session=False)
    db.commit()
    return {"deleted": count, "cutoff": cutoff.isoformat()}


def replay_failed_events(db: Session, *, provider: str | None, limit: int) -> dict:
    query = db.query(BillingWebhookEvent).filter(
        BillingWebhookEvent.status == "failed",
        BillingWebhookEvent.dead_letter.is_(False),
    )
    if provider:
        query = query.filter(BillingWebhookEvent.provider == provider)
    rows = query.order_by(BillingWebhookEvent.id.asc()).limit(limit).all()
    results = []
    for row in rows:
        try:
            results.append({"id": row.id, **replay_webhook_event(db, event_id=row.id)})
        except HTTPException as exc:
            results.append({"id": row.id, "status": "failed", "error": str(exc.detail)})
    return {"total": len(results), "items": results}


def build_metrics(db: Session, *, from_ts, to_ts) -> dict:
    base = db.query(Subscription)
    if from_ts:
        base = base.filter(Subscription.updated_at >= from_ts)
    if to_ts:
        base = base.filter(Subscription.updated_at <= to_ts)
    subs = base.all()
    status_counts = Counter([s.status for s in subs])
    active = sum(1 for s in subs if s.entitlement_active)
    new_subs = (
        sum(1 for s in subs if from_ts and s.created_at >= from_ts)
        if from_ts
        else len(subs)
    )
    canceled = status_counts.get("canceled", 0)
    failed_query = db.query(BillingWebhookEvent).filter(
        BillingWebhookEvent.status == "failed"
    )
    if from_ts:
        failed_query = failed_query.filter(BillingWebhookEvent.received_at >= from_ts)
    if to_ts:
        failed_query = failed_query.filter(BillingWebhookEvent.received_at <= to_ts)
    webhook_failed_count = failed_query.count()
    prices = {"pro_monthly": 29, "test_plan": 0}
    unknown = [
        s.plan_code for s in subs if s.entitlement_active and s.plan_code not in prices
    ]
    if unknown:
        mrr_estimate = None
        mrr_reason = "Unknown plan mapping"
    else:
        mrr_estimate = sum(
            prices.get(s.plan_code, 0) for s in subs if s.entitlement_active
        )
        mrr_reason = None
    return {
        "active_subscriptions": active,
        "new_subscriptions": new_subs,
        "canceled_subscriptions": canceled,
        "trialing_count": status_counts.get("trialing", 0),
        "past_due_count": status_counts.get("past_due", 0),
        "webhook_failed_count": webhook_failed_count,
        "mrr_estimate": mrr_estimate,
        "mrr_reason": mrr_reason,
    }
