"""Telegram command handlers for the polling bot."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from casino_bot.db.models import GameRound, TokenAccount
from casino_bot.db.session import SessionLocal, check_database_ready
from casino_bot.games.service import GameEngineRejected, run_game_detailed
from casino_bot.settings import settings
from casino_bot.telegram_bot.flip_idempotency import (
    callback_idempotency_key,
    command_idempotency_key,
)
from casino_bot.telegram_bot import game_texts
from casino_bot.telegram_bot.rate_limit import allow_flip_action, allow_flip_prompt
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


@dataclass(frozen=True)
class _FlipSnapshot:
    """ORM-safe snapshot of a flip round after commit (session may be closed)."""

    status: str
    details: dict[str, Any] | None
    balance_line: str
    user_id: int
    bet_amount: int
    idempotent_replay: bool


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


def _flip_reply_from_snapshot(snap: _FlipSnapshot) -> str:
    if snap.status == "rejected":
        body = game_texts.flip_rejected_round_user_message(snap.details)
        if snap.idempotent_replay:
            body += "\n\n(Already processed — duplicate tap.)"
        return body
    if snap.status != "committed":
        return game_texts.flip_unexpected_error_message()
    details = snap.details or {}
    outcome = details.get("outcome")
    if outcome not in ("win", "lose"):
        return game_texts.flip_unexpected_error_message()
    return game_texts.flip_result_compact(
        stake_tokens=snap.bet_amount,
        outcome=outcome,
        balance_line=snap.balance_line,
        idempotent_replay=snap.idempotent_replay,
    )


def _flip_work(
    *,
    telegram_user_id: int,
    bet_amount: int,
    idempotency_key: str,
) -> _FlipSnapshot:
    db = SessionLocal()
    try:
        user = ensure_telegram_user(db, telegram_user_id=telegram_user_id)
        gr, idempotent_replay = run_game_detailed(
            db,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=bet_amount,
            idempotency_key=idempotency_key,
            actor="telegram_bot",
        )
        balance_line = resolve_balance_reply(db, user_id=user.id)
        db.commit()
        raw = gr.details_json
        details_copy = dict(raw) if isinstance(raw, dict) else None
        return _FlipSnapshot(
            status=str(gr.status),
            details=details_copy,
            balance_line=balance_line,
            user_id=user.id,
            bet_amount=bet_amount,
            idempotent_replay=idempotent_replay,
        )
    except GameEngineRejected:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _flip_quick_stake_amounts(*, balance: float) -> list[int]:
    presets = (1, 5, 10)
    return [
        a
        for a in presets
        if settings.COIN_FLIP_MIN_BET <= a <= settings.COIN_FLIP_MAX_BET
        and balance + 1e-9 >= float(a)
    ]


def _flip_keyboard_prompt_work(telegram_user_id: int) -> tuple[list[int], str]:
    db = SessionLocal()
    try:
        user = ensure_telegram_user(db, telegram_user_id=telegram_user_id)
        acc = db.query(TokenAccount).filter(TokenAccount.user_id == user.id).first()
        bal = float(acc.balance) if acc is not None else 0.0
        db.commit()
        amounts = _flip_quick_stake_amounts(balance=bal)
        line = resolve_balance_reply(db, user_id=user.id)
        return amounts, line
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _format_round_ts_utc(dt: datetime | None) -> str:
    if dt is None:
        return "?"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def rounds_history_message(db: Session, *, user_id: int) -> str:
    """Last committed coin_flip rounds for one internal ``user_id`` (tests may pass SQLite)."""
    limit = settings.TELEGRAM_ROUNDS_HISTORY_LIMIT
    rows = (
        db.query(GameRound)
        .filter(
            GameRound.user_id == user_id,
            GameRound.game_id == "coin_flip",
            GameRound.status == "committed",
        )
        .order_by(desc(GameRound.committed_at))
        .limit(limit)
        .all()
    )
    if not rows:
        return game_texts.rounds_empty_message()
    lines = [game_texts.rounds_history_header(limit=limit)]
    for gr in rows:
        details = gr.details_json if isinstance(gr.details_json, dict) else {}
        outcome = details.get("outcome", "?")
        rid = (gr.round_id or "")[:8]
        ts = _format_round_ts_utc(gr.committed_at)
        lines.append(
            f"{ts} | bet={gr.bet_amount:g} | {outcome} | Δ={gr.payout_delta:g} | #{rid}"
        )
    return "\n".join(lines)


def _rounds_history_work(telegram_user_id: int) -> str:
    db = SessionLocal()
    try:
        user = get_user_by_telegram_id(db, telegram_user_id)
        if user is None:
            return NOT_LINKED_BALANCE
        return rounds_history_message(db, user_id=user.id)
    finally:
        db.close()


def _log_flip_engine_reject(
    *,
    command: str,
    telegram_user_id: int,
    user_id_log: int | str,
    bet_amount: int,
    idem_h: str,
    exc: GameEngineRejected,
) -> None:
    cooldown_s = "-"
    if exc.code == "cooldown_active" and exc.cooldown_remaining_seconds is not None:
        cooldown_s = str(int(exc.cooldown_remaining_seconds))
    _log.info(
        "telegram_flip command=%s telegram_user_id=%s user_id=%s bet=%s idem_hash=%s "
        "rejected_code=%s cooldown_remaining_seconds=%s",
        command,
        telegram_user_id,
        user_id_log,
        bet_amount,
        idem_h,
        exc.code,
        cooldown_s,
    )


def _flip_log_outcome(details: dict[str, Any] | None, *, status: str) -> str:
    # Rejected rounds merge prior game `details` (e.g. outcome=lose) with rejection_reason;
    # do not report that stale outcome as the round result.
    if status == "rejected":
        return "rejected"
    if status != "committed":
        return "-"
    if not details:
        return "-"
    return str(details.get("outcome", "-"))


async def cmd_flip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None or tid is None:
        return

    if not context.args:
        if not allow_flip_prompt(tid):
            _log.warning(
                "telegram_flip rate_limited telegram_user_id=%s scope=flip_prompt",
                tid,
            )
            await msg.reply_text(game_texts.TELEGRAM_RATE_LIMITED_MESSAGE)
            return
        try:
            quick_amounts, balance_line = await asyncio.to_thread(
                _flip_keyboard_prompt_work, tid
            )
        except Exception:
            _log.exception(
                "telegram_flip_prompt_failed telegram_user_id=%s update_id=%s",
                tid,
                update.update_id,
            )
            await msg.reply_text(game_texts.flip_unexpected_error_message())
            return

        caption = game_texts.flip_keyboard_caption()
        if not quick_amounts:
            body = f"{caption}\n\n{game_texts.flip_no_quick_stakes_message()}\n\n{balance_line}"
            await msg.reply_text(body)
        else:
            row = [
                InlineKeyboardButton(
                    str(a), callback_data=f"{_FLIP_CALLBACK_PREFIX}{a}"
                )
                for a in quick_amounts
            ]
            keyboard = InlineKeyboardMarkup([row])
            body = f"{caption}\n\n{balance_line}"
            await msg.reply_text(body, reply_markup=keyboard)
        _log.info(
            "telegram_flip_prompt telegram_user_id=%s update_id=%s quick_stakes=%s",
            tid,
            update.update_id,
            ",".join(str(a) for a in quick_amounts) if quick_amounts else "-",
        )
        return

    try:
        bet_amount = int(context.args[0])
    except (TypeError, ValueError):
        await msg.reply_text(game_texts.flip_usage_hint())
        return

    if not allow_flip_action(tid):
        _log.warning(
            "telegram_flip rate_limited telegram_user_id=%s scope=flip_command_bet",
            tid,
        )
        await msg.reply_text(game_texts.TELEGRAM_RATE_LIMITED_MESSAGE)
        return

    idem = command_idempotency_key(telegram_user_id=tid, update_id=update.update_id)
    idem_h = _idem_log_fragment(idem)

    def work() -> _FlipSnapshot:
        return _flip_work(
            telegram_user_id=tid,
            bet_amount=bet_amount,
            idempotency_key=idem,
        )

    try:
        snap = await asyncio.to_thread(work)
    except GameEngineRejected as exc:
        uid_log = await asyncio.to_thread(_lookup_user_id_for_log, tid)
        _log_flip_engine_reject(
            command="flip",
            telegram_user_id=tid,
            user_id_log=uid_log,
            bet_amount=bet_amount,
            idem_h=idem_h,
            exc=exc,
        )
        await msg.reply_text(
            game_texts.game_engine_rejected_user_message(
                exc.code,
                cooldown_remaining_seconds=exc.cooldown_remaining_seconds,
            )
        )
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

    body = _flip_reply_from_snapshot(snap)
    _log.info(
        "telegram_flip command=flip telegram_user_id=%s user_id=%s game_id=coin_flip bet=%s "
        "idem_hash=%s outcome=%s status=%s idempotent_replay=%s",
        tid,
        snap.user_id,
        bet_amount,
        idem_h,
        _flip_log_outcome(snap.details, status=snap.status),
        snap.status,
        snap.idempotent_replay,
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

    if not allow_flip_action(tid):
        _log.warning(
            "telegram_flip rate_limited telegram_user_id=%s scope=flip_callback",
            tid,
        )
        text = game_texts.TELEGRAM_RATE_LIMITED_MESSAGE
        try:
            await query.edit_message_text(text)
        except BadRequest:
            await query.message.reply_text(text)
        return

    idem = callback_idempotency_key(
        telegram_user_id=tid, callback_query_id=str(query.id)
    )
    idem_h = _idem_log_fragment(idem)

    def work() -> _FlipSnapshot:
        return _flip_work(
            telegram_user_id=tid,
            bet_amount=bet_amount,
            idempotency_key=idem,
        )

    try:
        snap = await asyncio.to_thread(work)
    except GameEngineRejected as exc:
        uid_log = await asyncio.to_thread(_lookup_user_id_for_log, tid)
        _log_flip_engine_reject(
            command="flip_callback",
            telegram_user_id=tid,
            user_id_log=uid_log,
            bet_amount=bet_amount,
            idem_h=idem_h,
            exc=exc,
        )
        text = game_texts.game_engine_rejected_user_message(
            exc.code,
            cooldown_remaining_seconds=exc.cooldown_remaining_seconds,
        )
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

    body = _flip_reply_from_snapshot(snap)
    _log.info(
        "telegram_flip command=flip_callback telegram_user_id=%s user_id=%s game_id=coin_flip bet=%s "
        "idem_hash=%s outcome=%s status=%s idempotent_replay=%s",
        tid,
        snap.user_id,
        bet_amount,
        idem_h,
        _flip_log_outcome(snap.details, status=snap.status),
        snap.status,
        snap.idempotent_replay,
    )
    try:
        await query.edit_message_text(body)
    except BadRequest:
        await query.message.reply_text(body)


async def cmd_rounds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    tid = _telegram_user_id(update)
    if msg is None or tid is None:
        return

    try:
        body = await asyncio.to_thread(_rounds_history_work, tid)
    except Exception:
        _log.exception(
            "telegram_rounds_failed telegram_user_id=%s",
            tid,
        )
        await msg.reply_text(game_texts.flip_unexpected_error_message())
        return
    _log.info(
        "telegram_command command=rounds telegram_user_id=%s",
        tid,
    )
    await msg.reply_text(body)


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
