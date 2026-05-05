"""Shared admin login flow (used by legacy and /api/v1 routes)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from casino_bot.admin.security_service import (
    perform_admin_login as _perform_admin_login,
)
from casino_bot.core.security import verify_password as verify_password  # noqa: F401


def perform_admin_login(
    db: Session,
    *,
    username: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict:
    return _perform_admin_login(
        db,
        username=username,
        password=password,
        ip_address=ip_address,
        user_agent=user_agent,
    )
