"""Telegram command handlers for the polling bot."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from casino_bot.db.session import SessionLocal
from casino_bot.telegram_bot.texts import (
    NOT_LINKED_BALANCE,
    help_message,
    me_message,
    welcome_message,
)
from casino_bot.telegram_bot.user_ops import (
    ensure_telegram_user,
    get_user_by_telegram_id,
    resolve_balance_reply,
)

_log = logging.getLogger("casino_bot.telegram")


def _telegram_user_id(update: Update) -> int | None:
    user = update.effective_user
    return int(user.id) if user else None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None or tid is None:
        return

    def work() -> int:
        db = SessionLocal()
        try:
            user = ensure_telegram_user(db, telegram_user_id=tid)
            db.commit()
            return user.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    try:
        internal_id = await asyncio.to_thread(work)
    except Exception:
        _log.exception("telegram_start_failed telegram_user_id=%s", tid)
        await msg.reply_text("Sorry, something went wrong. Please try again later.")
        return
    _log.info(
        "telegram_command command=start telegram_user_id=%s user_id=%s",
        tid,
        internal_id,
    )
    await msg.reply_text(welcome_message(internal_user_id=internal_id))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None:
        return
    uid_log = "-"
    if tid is not None:
        uid_log = await asyncio.to_thread(_lookup_user_id_for_log, tid)
    _log.info(
        "telegram_command command=help telegram_user_id=%s user_id=%s",
        tid if tid is not None else "-",
        uid_log,
    )
    await msg.reply_text(help_message())


def _lookup_user_id_for_log(telegram_user_id: int) -> int | str:
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, telegram_user_id)
        return user.id if user is not None else "-"
    finally:
        db.close()


async def cmd_me(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None or tid is None:
        return

    def lookup() -> int | None:
        db = SessionLocal()
        try:
            user = get_user_by_telegram_id(db, tid)
            return user.id if user is not None else None
        finally:
            db.close()

    internal_id = await asyncio.to_thread(lookup)
    _log.info(
        "telegram_command command=me telegram_user_id=%s user_id=%s",
        tid,
        internal_id if internal_id is not None else "-",
    )
    await msg.reply_text(me_message(telegram_user_id=tid, internal_user_id=internal_id))


async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None or tid is None:
        return

    def work() -> tuple[str, int | None]:
        db = SessionLocal()
        try:
            user = get_user_by_telegram_id(db, tid)
            if user is None:
                return NOT_LINKED_BALANCE, None
            return resolve_balance_reply(db, user_id=user.id), user.id
        finally:
            db.close()

    text, internal_id = await asyncio.to_thread(work)
    _log.info(
        "telegram_command command=balance telegram_user_id=%s user_id=%s",
        tid,
        internal_id if internal_id is not None else "-",
    )
    await msg.reply_text(text)
