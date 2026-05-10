"""Startup checks for the Telegram polling runner."""

from __future__ import annotations

import re

from casino_bot.settings import Settings

# BotFather issues ``<numeric_bot_id>:<secret>`` (secret is typically ~35 chars, [A-Za-z0-9_-]).
_TOKEN_RE = re.compile(
    r"^[0-9]{6,}:[A-Za-z0-9_-]{30,}$",
)


def telegram_bot_token_shape_valid(token: str) -> bool:
    """True if ``token`` matches the usual Bot API token shape (local check only)."""
    return bool(_TOKEN_RE.fullmatch(token.strip()))


def telegram_polling_startup_error(cfg: Settings) -> str | None:
    """Return a human-readable error, or ``None`` if polling may start."""
    token = (cfg.TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        return (
            "TELEGRAM_BOT_TOKEN is not set. Add your bot token to the environment "
            "(see docs/telegram-local-run.md)."
        )
    if not telegram_bot_token_shape_valid(token):
        return (
            "TELEGRAM_BOT_TOKEN does not look like a real BotFather API token "
            "(expected digits, colon, then a long secret, e.g. `123456789:AAH…`). "
            "Replace documentation placeholders such as `TOKEN_FROM_BOTFATHER` with "
            "the value from @BotFather (/token)."
        )
    if not cfg.TELEGRAM_BOT_ENABLED:
        return (
            "TELEGRAM_BOT_ENABLED is false. Set TELEGRAM_BOT_ENABLED=true to start "
            "the polling runner. Keep it false in environments where Telegram must "
            "not run unless you intend to."
        )
    if cfg.ENVIRONMENT not in cfg.TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS:
        return (
            f"Telegram polling is not allowed for ENVIRONMENT={cfg.ENVIRONMENT!r}. "
            f"Allowed: {cfg.TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS!r}. "
            "Adjust TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS only if you explicitly "
            "accept polling in this environment."
        )
    return None
