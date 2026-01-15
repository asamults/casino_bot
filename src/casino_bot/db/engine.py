# src/casino_bot/db/engine.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import Engine
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://casino:secret@localhost:5432/casino_db",
)

engine: Engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)
