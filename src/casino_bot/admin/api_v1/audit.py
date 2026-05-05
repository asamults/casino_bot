"""Audit log listing (Admin API v1)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from casino_bot.admin.api_v1.schemas import AuditLogItemOut, AuditLogsListResponse
from casino_bot.admin.deps import admin_guard
from casino_bot.core.database import get_db
from casino_bot.services.audit_query_service import list_audit_logs

router = APIRouter(tags=["admin"])

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


@router.get("", response_model=AuditLogsListResponse)
def api_list_audit_logs(
    db: Session = Depends(get_db),
    _: dict = Depends(admin_guard()),
    skip: int = Query(0, ge=0),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    actor: str | None = Query(None),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
):
    rows, total = list_audit_logs(
        db,
        skip=skip,
        limit=limit,
        actor=actor,
        created_after=created_after,
        created_before=created_before,
    )
    items = TypeAdapter(list[AuditLogItemOut]).validate_python(rows)
    return AuditLogsListResponse(items=items, total=total)
