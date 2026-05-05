import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Prefer the real package under src/ when the repo root is mistakenly treated as a package.
_src = Path(__file__).resolve().parents[1] / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))


@pytest.fixture
def sqlite_session():
    """In-memory SQLite with FK enforcement for API integration-style tests."""
    from casino_bot.db.base import Base

    import casino_bot.admin.models  # noqa: F401
    import casino_bot.db.models  # noqa: F401

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _):
        dbapi_conn.execute("pragma foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()
