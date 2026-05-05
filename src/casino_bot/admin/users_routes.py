"""Admin CRUD for domain users and token adjustments."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from casino_bot.admin.deps import admin_guard
from casino_bot.core.database import get_db
from casino_bot.services import economy_service

router = APIRouter(tags=["admin"])


class UserCreateBody(BaseModel):
    internal_note: str | None = Field(None, max_length=512)
    telegram_user_id: int | None = None
    whatsapp_phone_e164: str | None = Field(None, max_length=32)
    billing_customer_id: str | None = Field(None, max_length=255)


class TokenAdjustBody(BaseModel):
    delta: float
    reason: str = Field(..., min_length=1, max_length=255)


@router.post("")
def admin_create_user(
    payload: UserCreateBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(admin_guard()),
):
    actor = str(admin.get("sub") or "unknown")
    try:
        user = economy_service.create_user(
            db,
            actor=actor,
            internal_note=payload.internal_note,
            telegram_user_id=payload.telegram_user_id,
            whatsapp_phone_e164=payload.whatsapp_phone_e164,
            billing_customer_id=payload.billing_customer_id,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unique constraint violated (telegram_user_id, whatsapp_phone_e164, or billing_customer_id)",
        ) from exc
    return {"id": user.id, "is_active": user.is_active}


@router.post("/{user_id}/tokens/adjust")
def admin_adjust_tokens(
    user_id: int,
    payload: TokenAdjustBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(admin_guard()),
):
    actor = str(admin.get("sub") or "unknown")
    try:
        account = economy_service.adjust_user_tokens(
            db,
            user_id=user_id,
            delta=payload.delta,
            reason=payload.reason,
            actor=actor,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return {"user_id": user_id, "balance": account.balance}
