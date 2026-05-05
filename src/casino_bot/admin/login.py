from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from casino_bot.admin.api_v1.login import LogoutAllBody, LogoutBody, RefreshBody
from casino_bot.admin.login_service import perform_admin_login
from casino_bot.admin.security_service import (
    revoke_all_sessions,
    revoke_refresh_session,
    refresh_admin_session,
)
from casino_bot.admin.deps import admin_guard
from casino_bot.admin.models import AdminUser
from casino_bot.core.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Legacy path; prefer ``POST /api/v1/admin/login`` for new clients."""
    return perform_admin_login(
        db,
        username=form.username,
        password=form.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh")
def refresh(
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
def logout(
    payload: LogoutBody,
    db: Session = Depends(get_db),
):
    revoke_refresh_session(
        db,
        refresh_token=payload.refresh_token,
        session_id=payload.session_id,
    )
    return {"status": "ok"}


@router.post("/logout-all")
def logout_all(
    payload: LogoutAllBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(admin_guard()),
):
    actor_email = str(admin.get("sub") or "unknown")
    actor_role = str(admin.get("role") or "")
    actor_user = db.query(AdminUser).filter_by(email=actor_email).first()
    if actor_user is None:
        return {"status": "ok", "revoked_sessions": 0}
    target_admin_user_id = actor_user.id
    if payload.admin_user_id is not None and actor_role == "superadmin":
        target_admin_user_id = payload.admin_user_id
    revoked = revoke_all_sessions(
        db, target_admin_user_id=target_admin_user_id, actor=actor_email
    )
    return {"status": "ok", "revoked_sessions": revoked}
