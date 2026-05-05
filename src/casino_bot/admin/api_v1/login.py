"""Admin OAuth2 password login (canonical path for new clients)."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from casino_bot.admin.login_service import perform_admin_login
from casino_bot.admin.security_service import (
    revoke_all_sessions,
    revoke_refresh_session,
    refresh_admin_session,
)
from casino_bot.admin.deps import admin_guard
from casino_bot.admin.models import AdminUser
from casino_bot.core.database import get_db

router = APIRouter(tags=["admin"])


class RefreshBody(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class LogoutBody(BaseModel):
    refresh_token: str | None = Field(default=None)
    session_id: str | None = Field(default=None)


class LogoutAllBody(BaseModel):
    admin_user_id: int | None = None


@router.post(
    "/login",
    summary="Admin login",
    description="Returns access+refresh token pair. Use `Authorization: Bearer <access_token>` on protected routes.",
)
def admin_login_v1(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    return perform_admin_login(
        db,
        username=form.username,
        password=form.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh")
def admin_refresh_v1(
    request: Request,
    payload: RefreshBody,
    db: Session = Depends(get_db),
):
    return refresh_admin_session(
        db,
        refresh_token=payload.refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/logout")
def admin_logout_v1(
    payload: LogoutBody,
    db: Session = Depends(get_db),
):
    ok = revoke_refresh_session(
        db,
        refresh_token=payload.refresh_token,
        session_id=payload.session_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok"}


@router.post("/logout-all")
def admin_logout_all_v1(
    payload: LogoutAllBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(admin_guard()),
):
    actor_email = str(admin.get("sub") or "unknown")
    actor_role = str(admin.get("role") or "")
    actor_user = db.query(AdminUser).filter_by(email=actor_email).first()
    if actor_user is None:
        raise HTTPException(status_code=401, detail="Invalid token")

    target_admin_user_id = actor_user.id
    if payload.admin_user_id is not None:
        if actor_role != "superadmin":
            raise HTTPException(status_code=403, detail="Superadmin role required")
        target_admin_user_id = payload.admin_user_id

    revoked = revoke_all_sessions(
        db, target_admin_user_id=target_admin_user_id, actor=actor_email
    )
    return {"status": "ok", "revoked_sessions": revoked}
