#!/usr/bin/env python3
"""Heuristic scan: users with unusually high committed coin_flip velocity (Phase 4B).

Cron-friendly; uses ``DATABASE_URL``. Does **not** emit per-user Prometheus labels.

Example::

    PYTHONPATH=src DATABASE_URL=postgresql+psycopg://... \\
      GAME_ACTIVITY_WINDOW_MINUTES=5 GAME_SUSPICIOUS_COMMITTED_ROUNDS_THRESHOLD=40 \\
      python scripts/ops/game_activity_scan.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

_log = logging.getLogger("casino_bot.ops.game_activity_scan")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )
    window_m = int(os.environ.get("GAME_ACTIVITY_WINDOW_MINUTES", "5"))
    threshold = int(os.environ.get("GAME_SUSPICIOUS_COMMITTED_ROUNDS_THRESHOLD", "45"))
    game_id = os.environ.get("GAME_ACTIVITY_GAME_ID", "coin_flip")

    try:
        from casino_bot.db.models import GameRound
        from casino_bot.db.session import SessionLocal
    except ImportError:
        _log.error(
            "Import failed — run from repo root with PYTHONPATH=src "
            "(see scripts/ops/game_activity_scan.py docstring)."
        )
        return 1

    since = datetime.now(timezone.utc) - timedelta(minutes=window_m)

    db = SessionLocal()
    try:
        rows = (
            db.query(GameRound.user_id, func.count())
            .filter(
                GameRound.game_id == game_id,
                GameRound.status == "committed",
                GameRound.committed_at.isnot(None),
                GameRound.committed_at >= since,
            )
            .group_by(GameRound.user_id)
            .having(func.count() > threshold)
            .order_by(func.count().desc())
            .all()
        )
        for uid, n in rows:
            _log.warning(
                "suspicious_game_velocity user_id=%s committed_rounds=%s "
                "window_min=%s threshold=%s game_id=%s",
                uid,
                n,
                window_m,
                threshold,
                game_id,
            )
        if not rows:
            _log.info(
                "game_activity_scan_ok window_min=%s threshold=%s game_id=%s",
                window_m,
                threshold,
                game_id,
            )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
