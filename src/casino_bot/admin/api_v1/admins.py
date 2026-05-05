"""Staff admin user management (superadmin only for writes)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import TypeAdapter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from casino_bot.admin.api_v1.schemas import (
    AdminCreateBody,
    AdminPatchBody,
    AdminPasswordResetBody,
    AdminUserOut,
    AdminsListResponse,
)
from casino_bot.admin.deps import admin_guard, superadmin_guard
from casino_bot.admin.rbac import ROLE_ADMIN, ROLE_SUPERADMIN
from casino_bot.core.database import get_db
from casino_bot.services import admin_accounts_service

router = APIRouter(tags=["admin"])


@router.get("", response_model=AdminsListResponse)
def api_list_admins(
    db: Session = Depends(get_db),
    _: dict = Depends(admin_guard()),
):
    rows = admin_accounts_service.list_admin_users(db)
    items = TypeAdapter(list[AdminUserOut]).validate_python(rows)
    return AdminsListResponse(items=items, total=len(items))


@router.post("", status_code=status.HTTP_201_CREATED)
def api_create_admin(
    payload: AdminCreateBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(superadmin_guard()),
):
    if payload.role not in (ROLE_ADMIN, ROLE_SUPERADMIN):
        raise HTTPException(status_code=422, detail="role must be admin or superadmin")
    actor = str(admin.get("sub") or "unknown")
    try:
        row = admin_accounts_service.create_admin_user(
            db,
            email=payload.email,
            password=payload.password,
            role=payload.role,
            actor_email=actor,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email already registered") from exc
    return AdminUserOut.model_validate(row)


@router.patch("/{admin_id}")
def api_patch_admin(
    admin_id: int,
    payload: AdminPatchBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(superadmin_guard()),
):
    if payload.role is None and payload.is_active is None:
        raise HTTPException(status_code=422, detail="Provide role and/or is_active")
    if payload.role is not None and payload.role not in (ROLE_ADMIN, ROLE_SUPERADMIN):
        raise HTTPException(status_code=422, detail="role must be admin or superadmin")
    actor = str(admin.get("sub") or "unknown")
    row = admin_accounts_service.get_admin_by_id(db, admin_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Admin not found")
    if payload.is_active is not None:
        admin_accounts_service.set_admin_active(
            db, admin_id=admin_id, is_active=payload.is_active, actor_email=actor
        )
    if payload.role is not None:
        admin_accounts_service.set_admin_role(
            db, admin_id=admin_id, role=payload.role, actor_email=actor
        )
    db.commit()
    updated = admin_accounts_service.get_admin_by_id(db, admin_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Admin not found")
    return AdminUserOut.model_validate(updated)


@router.post("/{admin_id}/password")
def api_reset_admin_password(
    admin_id: int,
    payload: AdminPasswordResetBody,
    db: Session = Depends(get_db),
    admin: dict = Depends(superadmin_guard()),
):
    actor = str(admin.get("sub") or "unknown")
    row = admin_accounts_service.reset_admin_password(
        db,
        admin_id=admin_id,
        new_password=payload.new_password,
        actor_email=actor,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Admin not found")
    db.commit()
    return {"status": "ok"}
