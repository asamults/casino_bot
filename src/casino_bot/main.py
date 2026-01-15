"""
from casino_bot.admin.router import router as admin_router
from casino_bot.core.wait_for_db import wait_for_db
from fastapi import FastAPI

wait_for_db()  # ждем готовности базы перед стартом API

app = FastAPI(
    title="Casino Bot (Non-Gambling, UK Legal-by-Design)",
    version="0.1.0",
)

app.include_router(admin_router)


@app.get("/healt")
async def root():
    return {"status": "ok"}
"""

from fastapi import FastAPI
from src.casino_bot.db.base import engine, Base

app = FastAPI(title="Casino Bot API")

@app.on_event("startup")
async def startup():
    # Создаем все таблицы при старте
    Base.metadata.create_all(bind=engine)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
