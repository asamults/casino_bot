from __future__ import annotations

import uuid

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from casino_bot.settings import settings


class DrillFaultInjectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if settings.ENVIRONMENT == "production":
            return await call_next(request)

        raw = (settings.DRILL_FORCE_500_ON_PATH or "").strip()
        if not raw:
            return await call_next(request)

        paths = {p.strip() for p in raw.split(",") if p.strip()}
        if request.url.path not in paths:
            return await call_next(request)

        if not getattr(request.state, "request_id", None):
            request.state.request_id = str(uuid.uuid4())

        raise HTTPException(
            status_code=500,
            detail={
                "code": "DRILL_FORCED_500",
                "message": "Forced 500 for operational drill",
                "request_id": getattr(request.state, "request_id", None),
                "path": request.url.path,
            },
        )
