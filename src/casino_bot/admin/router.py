from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from casino_bot.core.database import get_db
from casino_bot.admin.deps import admin_guard

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(admin_guard)],
)

@router.get("/ping")
def admin_ping(db: Session = Depends(get_db)):
    return {"status": "ok"}
