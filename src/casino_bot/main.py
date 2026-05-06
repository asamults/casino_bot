import logging

import anyio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from casino_bot.admin.api_v1.router import router as api_v1_router
from casino_bot.admin.login import router as admin_login_router
from casino_bot.admin.router import router as admin_router
from casino_bot.billing.api_v1 import router as billing_api_v1_router
from casino_bot.compliance.violations import ComplianceViolation
from casino_bot.core.error_responses import (
    COMPLIANCE_VIOLATION_CODE,
    INTERNAL_ERROR_CODE,
)
from casino_bot.core.http_middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
)
from casino_bot.core.logging_config import configure_logging
from casino_bot.core.security_middleware import (
    InMemoryRateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from casino_bot.db.session import check_database_ready
from casino_bot.core.metrics import db_ready_state
from casino_bot.settings import settings

from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

configure_logging(settings.LOG_LEVEL)
_logger = logging.getLogger("casino_bot.main")

app = FastAPI(
    title="Casino Bot API",
    description=(
        "HTTP API for casino operations automation (non-gambling, "
        "UK legal-by-design). Admin surface: **/api/v1/admin/** (preferred); "
        "legacy **/admin/** routes remain for one release (same JWT)."
    ),
    version="0.2.0",
    openapi_tags=[
        {"name": "health", "description": "Liveness and readiness probes"},
        {
            "name": "admin",
            "description": "Admin authentication and management (v1 under /api/v1/admin)",
        },
    ],
)

if settings.CORS_ALLOW_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

if settings.ENVIRONMENT == "production":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

app.include_router(api_v1_router)
app.include_router(billing_api_v1_router)
app.include_router(admin_login_router)
app.include_router(admin_router)


@app.exception_handler(ComplianceViolation)
async def compliance_violation_handler(request, exc: ComplianceViolation):
    return JSONResponse(
        status_code=409,
        content={
            "detail": str(exc),
            "code": COMPLIANCE_VIOLATION_CODE,
        },
    )


if settings.ENVIRONMENT == "production":
    from fastapi.exception_handlers import (
        http_exception_handler,
        request_validation_exception_handler,
    )
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(Exception)
    async def production_unhandled_exception_handler(request, exc: Exception):
        if isinstance(exc, HTTPException):
            return await http_exception_handler(request, exc)
        if isinstance(exc, RequestValidationError):
            return await request_validation_exception_handler(request, exc)
        rid = getattr(request.state, "request_id", None)
        _logger.exception("Unhandled error (request_id=%s)", rid, exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "code": INTERNAL_ERROR_CODE,
            },
        )


@app.get(
    "/health",
    tags=["health"],
    summary="Liveness",
    description="Returns if the process is running (does not check dependencies).",
)
async def health_check():
    return {"status": "ok"}


@app.get(
    "/ready",
    tags=["health"],
    summary="Readiness",
    description="Checks database connectivity; returns 503 if the DB is unavailable.",
)
async def readiness():
    try:
        await anyio.to_thread.run_sync(check_database_ready)
        db_ready_state.set(1)
    except Exception as exc:
        db_ready_state.set(0)
        _logger.warning("Readiness check failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
