"""Admin API version 1 — mounted under ``/api/v1``."""

from fastapi import APIRouter

from casino_bot.admin.api_v1 import audit, admins, billing, login, me, ping, users

router = APIRouter(prefix="/api/v1")

router.include_router(login.router, prefix="/admin")
router.include_router(ping.router, prefix="/admin")
router.include_router(users.router, prefix="/admin/users")
router.include_router(audit.router, prefix="/admin/audit-logs")
router.include_router(admins.router, prefix="/admin/admins")
router.include_router(me.router, prefix="/admin/me")
router.include_router(billing.router, prefix="/admin/billing")
