from __future__ import annotations

import argparse
import os
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import ArgumentError, OperationalError

DEFAULT_DEV_DATABASE_URL = "postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db"


def wait_for_db(*, database_url: str, timeout_s: float, interval_s: float) -> None:
    """Block until DB is reachable, or raise with a clear error."""
    database_url = (database_url or "").strip()
    if not database_url:
        raise ValueError(
            "DATABASE_URL is required (tip: `export DATABASE_URL=...` or run with "
            f"`DATABASE_URL={DEFAULT_DEV_DATABASE_URL}` for local compose)"
        )

    deadline = time.monotonic() + max(0.0, timeout_s)

    while True:
        try:
            engine = create_engine(
                database_url,
                future=True,
                pool_pre_ping=True,
                connect_args={"connect_timeout": 2}
                if database_url.lower().startswith(("postgresql", "postgres"))
                else {},
            )
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except (ArgumentError, OperationalError, OSError, ValueError) as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Database not ready after {timeout_s:.0f}s: {exc}"
                ) from exc
            time.sleep(max(0.1, interval_s))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Wait for DATABASE_URL to become reachable (used before Alembic/app start)."
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Database URL (default: env DATABASE_URL).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.environ.get("DB_WAIT_TIMEOUT_SECONDS", "30")),
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=float(os.environ.get("DB_WAIT_INTERVAL_SECONDS", "1")),
    )
    args = parser.parse_args(argv)
    try:
        wait_for_db(
            database_url=args.database_url,
            timeout_s=args.timeout_seconds,
            interval_s=args.interval_seconds,
        )
    except Exception as exc:
        print(f"DB wait failed: {exc}", file=sys.stderr)
        return 2

    print("OK: database is ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
