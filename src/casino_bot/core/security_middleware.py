from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from casino_bot.settings import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _get_limit(self, request: Request) -> tuple[str | None, int]:
        path = request.url.path
        method = request.method.upper()
        ip = request.client.host if request.client else "unknown"

        if path in ("/api/v1/admin/login", "/admin/login"):
            # Keep middleware-level key body-agnostic to avoid consuming request stream.
            # Account-level brute-force protection is enforced in admin.security_service.
            return f"login:{ip}", settings.LOGIN_RATE_LIMIT_PER_MINUTE
        if path in ("/api/v1/admin/refresh", "/admin/refresh"):
            auth = request.headers.get("Authorization", "").strip() or "no-auth"
            return f"refresh:{ip}:{auth}", settings.REFRESH_RATE_LIMIT_PER_MINUTE
        if path == "/api/v1/billing/checkout/session":
            user_id = request.headers.get("x-user-id", "unknown")
            return f"billing-checkout:{ip}:{user_id}", min(
                settings.WRITE_RATE_LIMIT_PER_MINUTE, 20
            )
        if path.startswith("/api/v1/admin") or path.startswith("/admin"):
            auth = request.headers.get("Authorization", "").strip() or "no-auth"
            limit = (
                settings.READ_RATE_LIMIT_PER_MINUTE
                if method == "GET"
                else settings.WRITE_RATE_LIMIT_PER_MINUTE
            )
            return f"admin:{method}:{ip}:{auth}", limit
        return None, 0

    async def dispatch(self, request: Request, call_next) -> Response:
        key, limit = self._get_limit(request)
        if not key:
            return await call_next(request)

        is_login_path = request.url.path in ("/api/v1/admin/login", "/admin/login")
        now = time.monotonic()
        window = 60.0
        queue = self._hits[key]
        while queue and (now - queue[0]) > window:
            queue.popleft()
        if len(queue) >= limit:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
            )
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["X-RateLimit-Window"] = "60"
            return response

        response = await call_next(request)
        # Login throttle counts failed attempts only.
        if not is_login_path or response.status_code == 401:
            queue.append(now)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(queue)))
        response.headers["X-RateLimit-Window"] = "60"
        return response
