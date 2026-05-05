from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from casino_bot.admin.api_v1.schemas import BillingEventOut, BillingEventsListResponse
from casino_bot.admin.deps import superadmin_guard
from casino_bot.core.database import get_db
from casino_bot.services.billing_service import (
    build_metrics,
    list_billing_events,
    replay_failed_events,
    replay_webhook_event,
)

router = APIRouter(tags=["admin"])


@router.get("/events", response_model=BillingEventsListResponse)
def api_list_billing_events(
    db: Session = Depends(get_db),
    _: dict = Depends(superadmin_guard()),
    provider: str | None = Query(None),
    status: str | None = Query(None),
    dead_letter: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    rows, total = list_billing_events(
        db,
        provider=provider,
        status=status,
        dead_letter=dead_letter,
        skip=skip,
        limit=limit,
    )
    items = TypeAdapter(list[BillingEventOut]).validate_python(rows)
    return BillingEventsListResponse(items=items, total=total)


@router.post("/events/{event_id}/replay")
def api_replay_billing_event(
    event_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(superadmin_guard()),
):
    return replay_webhook_event(db, event_id=event_id)


@router.post("/events/replay-failed")
def api_replay_failed_events(
    db: Session = Depends(get_db),
    _: dict = Depends(superadmin_guard()),
    provider: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    return replay_failed_events(db, provider=provider, limit=limit)


@router.get("/metrics")
def api_billing_metrics(
    db: Session = Depends(get_db),
    _: dict = Depends(superadmin_guard()),
    from_ts: datetime | None = Query(None, alias="from"),
    to_ts: datetime | None = Query(None, alias="to"),
):
    return build_metrics(db, from_ts=from_ts, to_ts=to_ts)
