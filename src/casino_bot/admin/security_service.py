from __future__ import annotations

import uuid
from datetime import timedelta, timezone

from fastapi import HTTPException, status
from jose import JWTError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from casino_bot.admin.models import AdminLoginLock, AdminSession, AdminUser
from casino_bot.core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    decode_token_of_type,
    hash_refresh_token,
    utcnow,
    verify_password,
)
from casino_bot.services.audit_service import audit_log
from casino_bot.settings import settings

INVALID_CREDENTIALS = "Invalid credentials"


def normalize_identity(raw: str) -> str:
    return (raw or "").strip().lower()


def _active_lock(
    db: Session, *, identity: str, ip_address: str | None
) -> AdminLoginLock | None:
    now = utcnow()
    query = db.query(AdminLoginLock).filter(AdminLoginLock.identity == identity)
    if ip_address:
        query = query.filter(
            or_(
                AdminLoginLock.ip_address == ip_address,
                AdminLoginLock.ip_address == "*",
            )
        )
    return query.filter(
        AdminLoginLock.locked_until.is_not(None), AdminLoginLock.locked_until > now
    ).first()


def assert_not_locked(db: Session, *, identity: str, ip_address: str | None) -> None:
    lock = _active_lock(db, identity=identity, ip_address=ip_address)
    if lock:
        audit_log(
            db,
            actor=identity or "unknown",
            action="login_lockout_blocked",
            details={"identity": identity, "ip_address": ip_address},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts",
        )


def _get_or_create_lock(
    db: Session, *, identity: str, ip_address: str
) -> AdminLoginLock:
    row = (
        db.query(AdminLoginLock)
        .filter_by(identity=identity, ip_address=ip_address)
        .first()
    )
    if row is None:
        row = AdminLoginLock(identity=identity, ip_address=ip_address)
        db.add(row)
        db.flush()
    return row


def record_login_failure(db: Session, *, identity: str, ip_address: str) -> None:
    now = utcnow()
    row = _get_or_create_lock(db, identity=identity, ip_address=ip_address)

    window_start = now - timedelta(seconds=settings.ATTEMPT_WINDOW_SECONDS)
    first_attempt_at = row.first_attempt_at
    if first_attempt_at is not None and first_attempt_at.tzinfo is None:
        first_attempt_at = first_attempt_at.replace(tzinfo=timezone.utc)

    if first_attempt_at is None or first_attempt_at < window_start:
        row.first_attempt_at = now
        row.attempts_count = 1
    else:
        row.attempts_count += 1
    row.last_attempt_at = now

    if row.attempts_count >= settings.MAX_LOGIN_ATTEMPTS:
        row.locked_until = now + timedelta(seconds=settings.LOCKOUT_SECONDS)
        audit_log(
            db,
            actor=identity or "unknown",
            action="login_lockout",
            details={"identity": identity, "ip_address": ip_address},
        )


def clear_login_failures(db: Session, *, identity: str) -> None:
    rows = db.query(AdminLoginLock).filter(AdminLoginLock.identity == identity).all()
    for row in rows:
        row.attempts_count = 0
        row.first_attempt_at = utcnow()
        row.last_attempt_at = utcnow()
        row.locked_until = None


def _create_session_and_tokens(
    db: Session,
    *,
    user: AdminUser,
    ip_address: str | None,
    user_agent: str | None,
    rotated_from_session_id: str | None = None,
) -> dict:
    session_id = str(uuid.uuid4())
    refresh_token, refresh_expires = create_refresh_token(user.email, session_id)
    refresh_hash = hash_refresh_token(refresh_token)
    session_row = AdminSession(
        id=session_id,
        admin_user_id=user.id,
        refresh_token_hash=refresh_hash,
        user_agent=user_agent,
        ip_address=ip_address,
        expires_at=refresh_expires,
        rotated_from_session_id=rotated_from_session_id,
        last_used_at=utcnow(),
    )
    db.add(session_row)
    access_token, _, access_expires = create_access_token(user.email, user.role)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": int((access_expires - utcnow()).total_seconds()),
        "refresh_token": refresh_token,
        "refresh_expires_in": int((refresh_expires - utcnow()).total_seconds()),
        "session_id": session_id,
    }


def perform_admin_login(
    db: Session,
    *,
    username: str,
    password: str,
    ip_address: str | None,
    user_agent: str | None,
) -> dict:
    identity = normalize_identity(username)
    safe_ip = ip_address or "unknown"
    assert_not_locked(db, identity=identity, ip_address=safe_ip)

    user = db.query(AdminUser).filter_by(email=identity).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(password, user.password_hash)
    ):
        record_login_failure(db, identity=identity, ip_address=safe_ip)
        audit_log(
            db,
            actor=identity or "unknown",
            action="login_failed",
            details={"email": identity, "ip_address": safe_ip},
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_CREDENTIALS
        )

    clear_login_failures(db, identity=identity)
    payload = _create_session_and_tokens(
        db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    audit_log(
        db,
        actor=user.email,
        action="login_success",
        details={
            "role": user.role,
            "ip_address": safe_ip,
            "session_id": payload["session_id"],
        },
    )
    db.commit()
    return payload


def _get_refresh_session(
    db: Session, *, refresh_token: str
) -> tuple[dict, AdminSession]:
    try:
        payload = decode_token_of_type(refresh_token, TOKEN_TYPE_REFRESH)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        ) from exc
    session_id = str(payload.get("sid") or "")
    refresh_hash = hash_refresh_token(refresh_token)
    row = db.query(AdminSession).filter(AdminSession.id == session_id).first()
    if row is None or row.refresh_token_hash != refresh_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    expires_at = row.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if row.revoked_at is not None or (
        expires_at is not None and expires_at <= utcnow()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired",
        )
    return payload, row


def refresh_admin_session(
    db: Session,
    *,
    refresh_token: str,
    ip_address: str | None,
    user_agent: str | None,
) -> dict:
    payload, row = _get_refresh_session(db, refresh_token=refresh_token)
    user = db.query(AdminUser).filter_by(id=row.admin_user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    row.revoked_at = utcnow()
    row.last_used_at = utcnow()
    issued = _create_session_and_tokens(
        db,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        rotated_from_session_id=row.id,
    )
    audit_log(
        db,
        actor=user.email,
        action="refresh",
        details={
            "session_id": row.id,
            "new_session_id": issued["session_id"],
            "sid_claim": payload.get("sid"),
        },
    )
    db.commit()
    return issued


def revoke_refresh_session(
    db: Session, *, refresh_token: str | None = None, session_id: str | None = None
) -> bool:
    row: AdminSession | None = None
    if refresh_token:
        _, row = _get_refresh_session(db, refresh_token=refresh_token)
    elif session_id:
        row = db.query(AdminSession).filter(AdminSession.id == session_id).first()
        if row is None or row.revoked_at is not None or row.expires_at <= utcnow():
            return False
    else:
        return False

    row.revoked_at = utcnow()
    row.last_used_at = utcnow()
    user = db.query(AdminUser).filter_by(id=row.admin_user_id).first()
    actor = user.email if user else "unknown"
    audit_log(db, actor=actor, action="logout", details={"session_id": row.id})
    db.commit()
    return True


def revoke_all_sessions(db: Session, *, target_admin_user_id: int, actor: str) -> int:
    now = utcnow()
    rows = (
        db.query(AdminSession)
        .filter(
            AdminSession.admin_user_id == target_admin_user_id,
            AdminSession.revoked_at.is_(None),
            AdminSession.expires_at > now,
        )
        .all()
    )
    for row in rows:
        row.revoked_at = now
        row.last_used_at = now
    audit_log(
        db,
        actor=actor,
        action="logout_all",
        details={
            "target_admin_user_id": target_admin_user_id,
            "revoked_count": len(rows),
        },
    )
    db.commit()
    return len(rows)
