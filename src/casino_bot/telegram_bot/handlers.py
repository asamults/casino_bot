"""Telegram command handlers for the polling bot."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from casino_bot.db.models import GameRound
from casino_bot.db.session import SessionLocal, check_database_ready
from casino_bot.games.service import GameEngineRejected, run_game
from casino_bot.settings import settings
from casino_bot.telegram_bot.flip_idempotency import (
    callback_idempotency_key,
    command_idempotency_key,
)
from casino_bot.telegram_bot import game_texts
from casino_bot.telegram_bot.texts import (
    NOT_LINKED_BALANCE,
    NOT_LINKED_PROFILE,
    admin_message,
    help_message,
    me_message,
    profile_message,
    status_summary_text,
    support_reply,
    welcome_message,
)
from casino_bot.telegram_bot.user_ops import (
    ensure_telegram_user,
    get_user_by_telegram_id,
    resolve_balance_reply,
)

_log = logging.getLogger("casino_bot.telegram")

_FLIP_CALLBACK_PREFIX = "flip:"


def _idem_log_fragment(idempotency_key: str) -> str:
    return hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]


def _telegram_user_id(update: Update) -> int | None:
    user = update.effective_user
    return int(user.id) if user else None


def database_ready_for_status() -> bool:
    """Match GET /ready semantics (DB ping; drill flag in non-production)."""
    try:
        if settings.ENVIRONMENT != "production" and settings.DRILL_FORCE_DB_NOT_READY:
            return False
        check_database_ready()
        return True
    except Exception:
        return False


def _format_user_created_at(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    return dt.isoformat(timespec="seconds")


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


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None:
        return
    uid_log = "-"
    if tid is not None:
        uid_log = await asyncio.to_thread(_lookup_user_id_for_log, tid)

    db_ready = await asyncio.to_thread(database_ready_for_status)
    _log.info(
        "telegram_command command=status telegram_user_id=%s user_id=%s",
        tid if tid is not None else "-",
        uid_log,
    )
    await msg.reply_text(status_summary_text(database_ready=db_ready))


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None or tid is None:
        return

    def lookup():
        db = SessionLocal()
        try:
            user = get_user_by_telegram_id(db, tid)
            if user is None:
                return None, None
            return user, user.id
        finally:
            db.close()

    user_row, internal_id = await asyncio.to_thread(lookup)
    _log.info(
        "telegram_command command=profile telegram_user_id=%s user_id=%s",
        tid,
        internal_id if internal_id is not None else "-",
    )
    if user_row is None:
        await msg.reply_text(NOT_LINKED_PROFILE)
        return
    await msg.reply_text(
        profile_message(
            internal_user_id=user_row.id,
            telegram_user_id=tid,
            is_active=bool(user_row.is_active),
            created_at_iso=_format_user_created_at(user_row.created_at),
        )
    )


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None:
        return
    uid_log = "-"
    if tid is not None:
        uid_log = await asyncio.to_thread(_lookup_user_id_for_log, tid)
    _log.info(
        "telegram_command command=admin telegram_user_id=%s user_id=%s",
        tid if tid is not None else "-",
        uid_log,
    )
    await msg.reply_text(admin_message())


async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None:
        return
    uid_log = "-"
    if tid is not None:
        uid_log = await asyncio.to_thread(_lookup_user_id_for_log, tid)
    _log.info(
        "telegram_command command=support telegram_user_id=%s user_id=%s",
        tid if tid is not None else "-",
        uid_log,
    )
    body = support_reply(
        support_text=settings.TELEGRAM_SUPPORT_TEXT,
        contact_url=settings.SUPPORT_CONTACT_URL,
    )
    await msg.reply_text(body)


def _flip_reply_from_round(gr: GameRound, *, balance_line: str) -> str:
    if gr.status == "rejected":
        return game_texts.flip_rejected_round_user_message(
            gr.details_json if isinstance(gr.details_json, dict) else None
        )
    if gr.status != "committed":
        return game_texts.flip_unexpected_error_message()
    details = gr.details_json if isinstance(gr.details_json, dict) else {}
    outcome = details.get("outcome")
    if outcome == "win":
        return game_texts.flip_win_message(balance_line=balance_line)
    if outcome == "lose":
        return game_texts.flip_lose_message(balance_line=balance_line)
    return game_texts.flip_unexpected_error_message()


def _flip_work(
    *,
    telegram_user_id: int,
    bet_amount: int,
    idempotency_key: str,
) -> tuple[GameRound, str, int]:
    db = SessionLocal()
    try:
        user = ensure_telegram_user(db, telegram_user_id=telegram_user_id)
        gr = run_game(
            db,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=bet_amount,
            idempotency_key=idempotency_key,
            actor="telegram_bot",
        )
        balance_line = resolve_balance_reply(db, user_id=user.id)
        db.commit()
        return gr, balance_line, user.id
    except GameEngineRejected:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _flip_log_outcome(gr: GameRound) -> str:
    if not isinstance(gr.details_json, dict):
        return "-"
    return str(gr.details_json.get("outcome", "-"))


async def cmd_flip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None or tid is None:
        return

    if not context.args:
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "1", callback_data=f"{_FLIP_CALLBACK_PREFIX}1"
                    ),
                    InlineKeyboardButton(
                        "5", callback_data=f"{_FLIP_CALLBACK_PREFIX}5"
                    ),
                    InlineKeyboardButton(
                        "10", callback_data=f"{_FLIP_CALLBACK_PREFIX}10"
                    ),
                ]
            ]
        )
        await msg.reply_text(game_texts.flip_keyboard_caption(), reply_markup=keyboard)
        _log.info(
            "telegram_flip_prompt telegram_user_id=%s update_id=%s",
            tid,
            update.update_id,
        )
        return

    try:
        bet_amount = int(context.args[0])
    except (TypeError, ValueError):
        await msg.reply_text(game_texts.flip_usage_hint())
        return

    idem = command_idempotency_key(telegram_user_id=tid, update_id=update.update_id)
    idem_h = _idem_log_fragment(idem)

    def work() -> tuple[GameRound, str, int]:
        return _flip_work(
            telegram_user_id=tid,
            bet_amount=bet_amount,
            idempotency_key=idem,
        )

    try:
        gr, balance_line, internal_uid = await asyncio.to_thread(work)
    except GameEngineRejected as exc:
        uid_log = await asyncio.to_thread(_lookup_user_id_for_log, tid)
        _log.info(
            "telegram_flip command=flip telegram_user_id=%s user_id=%s bet=%s idem_hash=%s rejected_code=%s",
            tid,
            uid_log,
            bet_amount,
            idem_h,
            exc.code,
        )
        await msg.reply_text(game_texts.game_engine_rejected_user_message(exc.code))
        return
    except Exception:
        _log.exception(
            "telegram_flip_failed command=flip telegram_user_id=%s bet=%s idem_hash=%s",
            tid,
            bet_amount,
            idem_h,
        )
        await msg.reply_text(game_texts.flip_unexpected_error_message())
        return

    body = _flip_reply_from_round(gr, balance_line=balance_line)
    _log.info(
        "telegram_flip command=flip telegram_user_id=%s user_id=%s game_id=coin_flip bet=%s "
        "idem_hash=%s outcome=%s status=%s",
        tid,
        internal_uid,
        bet_amount,
        idem_h,
        _flip_log_outcome(gr),
        gr.status,
    )
    await msg.reply_text(body)


async def callback_flip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.message is None:
        return
    tid = _telegram_user_id(update)
    if tid is None:
        return

    data = (query.data or "").strip()
    if not data.startswith(_FLIP_CALLBACK_PREFIX):
        return

    try:
        bet_amount = int(data.split(":", 1)[1])
    except (IndexError, ValueError):
        await query.answer()
        return

    await query.answer()

    idem = callback_idempotency_key(
        telegram_user_id=tid, callback_query_id=str(query.id)
    )
    idem_h = _idem_log_fragment(idem)

    def work() -> tuple[GameRound, str, int]:
        return _flip_work(
            telegram_user_id=tid,
            bet_amount=bet_amount,
            idempotency_key=idem,
        )

    try:
        gr, balance_line, internal_uid = await asyncio.to_thread(work)
    except GameEngineRejected as exc:
        uid_log = await asyncio.to_thread(_lookup_user_id_for_log, tid)
        _log.info(
            "telegram_flip command=flip_callback telegram_user_id=%s user_id=%s bet=%s idem_hash=%s rejected_code=%s",
            tid,
            uid_log,
            bet_amount,
            idem_h,
            exc.code,
        )
        text = game_texts.game_engine_rejected_user_message(exc.code)
        try:
            await query.edit_message_text(text)
        except BadRequest:
            await query.message.reply_text(text)
        return
    except Exception:
        _log.exception(
            "telegram_flip_failed command=flip_callback telegram_user_id=%s bet=%s idem_hash=%s",
            tid,
            bet_amount,
            idem_h,
        )
        text = game_texts.flip_unexpected_error_message()
        try:
            await query.edit_message_text(text)
        except BadRequest:
            await query.message.reply_text(text)
        return

    body = _flip_reply_from_round(gr, balance_line=balance_line)
    _log.info(
        "telegram_flip command=flip_callback telegram_user_id=%s user_id=%s game_id=coin_flip bet=%s "
        "idem_hash=%s outcome=%s status=%s",
        tid,
        internal_uid,
        bet_amount,
        idem_h,
        _flip_log_outcome(gr),
        gr.status,
    )
    try:
        await query.edit_message_text(body)
    except BadRequest:
        await query.message.reply_text(body)


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
