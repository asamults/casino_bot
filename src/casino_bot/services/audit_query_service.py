"""Paginated audit log reads."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from casino_bot.admin.models import AuditLog


def list_audit_logs(
    db: Session,
    *,
    skip: int,
    limit: int,
    actor: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    q = db.query(AuditLog)
    if actor:
        q = q.filter(AuditLog.actor == actor)
    if created_after is not None:
        q = q.filter(AuditLog.created_at >= created_after)
    if created_before is not None:
        q = q.filter(AuditLog.created_at <= created_before)
    total = q.count()
    rows = q.order_by(AuditLog.id.desc()).offset(skip).limit(limit).all()
    return rows, total
