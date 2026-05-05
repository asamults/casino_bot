"""Admin user (staff) lifecycle — bcrypt hashes only, never log plaintext passwords."""

from __future__ import annotations

from sqlalchemy.orm import Session

from casino_bot.admin.models import AdminUser
from casino_bot.core.security import hash_password, verify_password
from casino_bot.services.audit_service import audit_log


def list_admin_users(db: Session) -> list[AdminUser]:
    return db.query(AdminUser).order_by(AdminUser.id).all()


def get_admin_by_email(db: Session, email: str) -> AdminUser | None:
    return db.query(AdminUser).filter(AdminUser.email == email).first()


def get_admin_by_id(db: Session, admin_id: int) -> AdminUser | None:
    return db.query(AdminUser).filter(AdminUser.id == admin_id).first()


def create_admin_user(
    db: Session,
    *,
    email: str,
    password: str,
    role: str,
    actor_email: str,
) -> AdminUser:
    row = AdminUser(
        email=email,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(row)
    db.flush()
    audit_log(
        db,
        actor=actor_email,
        action="admin_user_created",
        details={"target_email": email, "role": role, "admin_id": row.id},
    )
    return row


def set_admin_active(
    db: Session,
    *,
    admin_id: int,
    is_active: bool,
    actor_email: str,
) -> AdminUser | None:
    row = get_admin_by_id(db, admin_id)
    if row is None:
        return None
    row.is_active = is_active
    audit_log(
        db,
        actor=actor_email,
        action="admin_user_active_changed",
        details={"admin_id": admin_id, "is_active": is_active},
    )
    return row


def set_admin_role(
    db: Session,
    *,
    admin_id: int,
    role: str,
    actor_email: str,
) -> AdminUser | None:
    row = get_admin_by_id(db, admin_id)
    if row is None:
        return None
    row.role = role
    audit_log(
        db,
        actor=actor_email,
        action="admin_user_role_changed",
        details={"admin_id": admin_id, "role": role},
    )
    return row


def reset_admin_password(
    db: Session,
    *,
    admin_id: int,
    new_password: str,
    actor_email: str,
) -> AdminUser | None:
    row = get_admin_by_id(db, admin_id)
    if row is None:
        return None
    row.password_hash = hash_password(new_password)
    audit_log(
        db,
        actor=actor_email,
        action="admin_password_reset",
        details={"admin_id": admin_id},
    )
    return row


def change_own_password(
    db: Session,
    *,
    email: str,
    current_password: str,
    new_password: str,
) -> AdminUser | None:
    row = get_admin_by_email(db, email)
    if row is None or not row.is_active:
        return None
    if not verify_password(current_password, row.password_hash):
        return None
    row.password_hash = hash_password(new_password)
    audit_log(
        db,
        actor=email,
        action="admin_password_changed_self",
        details={},
    )
    return row
