"""Centralized audit trail writes (no FastAPI)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from casino_bot.admin.models import AuditLog


def audit_log(
    db: Session,
    *,
    actor: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append one ``audit_logs`` row. Caller controls transaction commit/rollback."""
    db.add(AuditLog(actor=actor, action=action, details=details))
