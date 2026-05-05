"""Database session dependency (re-export for stable imports)."""

from casino_bot.db.session import get_db

__all__ = ["get_db"]
