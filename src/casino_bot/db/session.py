from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from casino_bot.settings import settings

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)


def _readiness_connect_args(url: str) -> dict:
    u = (url or "").lower()
    if u.startswith("postgresql") or u.startswith("postgres"):
        return {"connect_timeout": 2}
    return {}


readiness_engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
    connect_args=_readiness_connect_args(settings.DATABASE_URL),
    pool_pre_ping=True,
)


def check_database_ready() -> None:
    """Raise if the database is not reachable (used by GET /ready)."""
    with readiness_engine.connect() as conn:
        conn.execute(text("SELECT 1"))


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
