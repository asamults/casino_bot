"""Current admin profile actions (Admin API v1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from casino_bot.admin.api_v1.schemas import MePasswordBody
from casino_bot.admin.deps import admin_guard
from casino_bot.core.database import get_db
from casino_bot.services import admin_accounts_service

router = APIRouter(tags=["admin"])


@router.post("/password")
def api_change_own_password(
    payload: MePasswordBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(admin_guard()),
):
    email = str(admin.get("sub") or "")
    row = admin_accounts_service.change_own_password(
        db,
        email=email,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    if row is None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    db.commit()
    return {"status": "ok"}
