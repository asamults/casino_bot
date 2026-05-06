from __future__ import annotations

import logging
from email.utils import format_datetime

from fastapi import Depends, HTTPException, Request, Response
from jose import JWTError
from sqlalchemy.orm import Session

from casino_bot.core.database import get_db
from casino_bot.core.metrics import legacy_admin_requests_total
from casino_bot.core.pii import mask_email
from casino_bot.core.security import TOKEN_TYPE_ACCESS, decode_token_of_type
from casino_bot.services.audit_service import audit_log
from casino_bot.settings import settings

logger = logging.getLogger("casino_bot.legacy")


def _successor_path(path: str) -> str:
    if path.startswith("/admin/") or path == "/admin":
        return path.replace("/admin", "/api/v1/admin", 1)
    return "/api/v1/admin"


def legacy_admin_guard(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    """Add deprecation headers + observability for legacy ``/admin/*`` routes.

    This is router-level and must not alter auth semantics.
    """
    if settings.LEGACY_ADMIN_DISABLE:
        raise HTTPException(status_code=410, detail="Legacy admin routes are disabled")

    successor = _successor_path(request.url.path)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = format_datetime(
        settings.LEGACY_ADMIN_SUNSET_AT, usegmt=True
    )
    response.headers["Link"] = f'<{successor}>; rel="successor-version"'

    legacy_admin_requests_total.labels(request.method, request.url.path).inc()

    actor = "unknown"
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token_of_type(token, TOKEN_TYPE_ACCESS)
            actor = str(payload.get("sub") or "unknown")
        except JWTError:
            actor = "unknown"

    rid = getattr(request.state, "request_id", "-")
    logger.warning(
        "legacy_admin_route_used request_id=%s method=%s path=%s successor=%s actor=%s legacy=%s",
        rid,
        request.method,
        request.url.path,
        successor,
        mask_email(actor),
        True,
    )

    audit_log(
        db,
        actor=actor,
        action="legacy_admin_route_used",
        details={
            "method": request.method,
            "path": request.url.path,
            "successor": successor,
            "request_id": rid,
            "sunset_at": settings.LEGACY_ADMIN_SUNSET_AT.isoformat(),
        },
    )
    db.commit()
