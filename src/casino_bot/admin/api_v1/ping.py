"""Simple authenticated probe for Admin API v1."""

from fastapi import APIRouter, Depends

from casino_bot.admin.deps import admin_guard

router = APIRouter(tags=["admin"])


@router.get("/ping", dependencies=[Depends(admin_guard())])
def api_v1_admin_ping():
    return {"status": "ok"}
