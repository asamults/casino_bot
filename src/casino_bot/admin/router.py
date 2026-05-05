from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from casino_bot.admin.deps import admin_guard
from casino_bot.admin.users_routes import router as admin_users_router
from casino_bot.core.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(admin_users_router, prefix="/users")


@router.get("/ping", dependencies=[Depends(admin_guard())])
def admin_ping(db: Session = Depends(get_db)):
    return {"status": "ok"}
