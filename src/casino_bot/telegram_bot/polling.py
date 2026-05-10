"""Run the Telegram bot with long polling (separate process from FastAPI)."""

from __future__ import annotations

import logging
import sys

from telegram.error import InvalidToken
from telegram.ext import Application, CommandHandler

from casino_bot.core.logging_config import configure_logging
from casino_bot.settings import settings
from casino_bot.telegram_bot.handlers import (
    cmd_balance,
    cmd_help,
    cmd_me,
    cmd_start,
)
from casino_bot.telegram_bot.preflight import telegram_polling_startup_error

_log = logging.getLogger("casino_bot.telegram.polling")


def build_application() -> Application:
    """Construct the PTB application (caller must validate preflight)."""
    token = settings.TELEGRAM_BOT_TOKEN.strip()
    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("me", cmd_me))
    application.add_handler(CommandHandler("balance", cmd_balance))
    return application


def main() -> None:
    configure_logging(settings.LOG_LEVEL)
    # Avoid logging full Telegram API URLs (they embed the bot token path segment).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    err = telegram_polling_startup_error(settings)
    if err:
        print(err, file=sys.stderr)
        raise SystemExit(1)
    _log.info(
        "telegram_polling_starting environment=%s",
        settings.ENVIRONMENT,
    )
    app = build_application()
    try:
        app.run_polling(drop_pending_updates=True)
    except InvalidToken:
        print(
            "Telegram rejected this bot token (revoked, mistyped, or wrong bot). "
            "Confirm TELEGRAM_BOT_TOKEN with @BotFather using /token. "
            "Do not paste or log the token in chat or tickets.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
