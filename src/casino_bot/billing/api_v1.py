from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from casino_bot.billing.deps import get_current_user_id
from casino_bot.billing.providers import PROVIDER_ADAPTERS
from casino_bot.core.database import get_db
from casino_bot.services.billing_service import (
    create_checkout_session,
    create_portal_link,
    create_webhook_event,
    get_user_subscription,
    request_cancel_subscription,
    request_resume_subscription,
    safe_process_webhook,
)
from casino_bot.core.pii import mask_token_like

logger = logging.getLogger("casino_bot.billing")
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


class CheckoutBody(BaseModel):
    plan_code: str = Field(..., min_length=1, max_length=64)
    success_url: str = Field(..., min_length=8, max_length=1024)
    cancel_url: str = Field(..., min_length=8, max_length=1024)


class PortalBody(BaseModel):
    return_url: str = Field(..., min_length=8, max_length=1024)


@router.post("/webhooks/{provider}")
async def billing_webhook(
    provider: str, request: Request, db: Session = Depends(get_db)
):
    adapter = PROVIDER_ADAPTERS.get(provider)
    if adapter is None:
        return {"status": "ignored"}

    raw_body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    event = adapter.parse_and_verify_webhook(headers=headers, raw_body=raw_body)
    row = create_webhook_event(db, event=event, raw_body=raw_body)
    if row is None:
        logger.info(
            "billing_webhook request_id=%s provider=%s external_event_id=%s status=%s",
            getattr(request.state, "request_id", "-"),
            provider,
            mask_token_like(event.external_event_id),
            "idempotent",
        )
        return {"status": "idempotent"}

    status = safe_process_webhook(db, event_row=row, event=event)
    logger.info(
        "billing_webhook request_id=%s provider=%s external_event_id=%s billing_event_id=%s status=%s dead_letter=%s attempts_count=%s",
        getattr(request.state, "request_id", "-"),
        provider,
        mask_token_like(event.external_event_id),
        row.id,
        status,
        row.dead_letter,
        row.attempts_count,
    )
    return {"status": status}


@router.post("/checkout/session")
def billing_checkout_session(
    payload: CheckoutBody,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return create_checkout_session(
        db,
        user_id=user_id,
        plan_code=payload.plan_code,
        success_url=payload.success_url,
        cancel_url=payload.cancel_url,
    )


@router.get("/me/subscription")
def billing_my_subscription(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    sub = get_user_subscription(db, user_id=user_id)
    if sub is None:
        return {"subscription": None}
    return {
        "subscription": {
            "id": sub.id,
            "provider": sub.provider,
            "status": sub.status,
            "plan_code": sub.plan_code,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "entitlement_active": sub.entitlement_active,
        }
    }


@router.post("/me/subscription/cancel")
def billing_cancel_subscription(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return request_cancel_subscription(db, user_id=user_id)


@router.post("/me/subscription/resume")
def billing_resume_subscription(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return request_resume_subscription(db, user_id=user_id)


@router.post("/me/portal")
def billing_create_portal(
    payload: PortalBody,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return create_portal_link(db, user_id=user_id, return_url=payload.return_url)
