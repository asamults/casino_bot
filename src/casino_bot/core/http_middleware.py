"""Request ID and HTTP access logging."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from casino_bot.core.metrics import http_request_duration_seconds, http_requests_total

REQUEST_ID_HEADER = "X-Request-ID"
_logger = logging.getLogger("casino_bot.request")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
        request_id = incoming or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000.0
        duration_s = duration_ms / 1000.0
        route = getattr(request.scope.get("route"), "path", request.url.path)  # type: ignore[union-attr]
        request_id = getattr(request.state, "request_id", "-")

        http_requests_total.labels(
            request.method, route, str(response.status_code)
        ).inc()
        http_request_duration_seconds.labels(request.method, route).observe(duration_s)

        _logger.info(
            "%s %s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response
