from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from casino_bot.services.billing_service import cleanup_old_webhook_events


def main() -> int:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL is required")
        return 2
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    with Session(engine) as db:
        result = cleanup_old_webhook_events(db)
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
