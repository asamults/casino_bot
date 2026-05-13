"""Telegram adapter: ``GamePresentation`` → PTB sends + audio metrics (Phase 6)."""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import CallbackQuery, Message
from telegram.error import BadRequest

from casino_bot.core.metrics import record_audio_delivery
from casino_bot.games.presentation import (
    build_flip_presentation,
    build_wheel_presentation,
)
from casino_bot.telegram_bot import game_texts

_log = logging.getLogger("casino_bot.telegram.delivery")


def _voice_asset_path(asset_id: str) -> Path | None:
    base = Path(__file__).resolve().parent / "assets" / "voice"
    for ext in (".oga", ".ogg", ".mp3"):
        candidate = base / f"{asset_id}{ext}"
        if candidate.is_file():
            return candidate
    return None


async def _send_voice_for_cue(
    anchor_message: Message, *, asset_id: str, cue_type: str
) -> bool:
    path = _voice_asset_path(asset_id)
    if path is None:
        record_audio_delivery(channel="telegram", cue_type=cue_type, status="fallback")
        return False
    try:
        with open(path, "rb") as handle:
            await anchor_message.reply_voice(voice=handle)
        record_audio_delivery(channel="telegram", cue_type=cue_type, status="sent")
        return True
    except Exception:
        _log.warning("telegram_voice_send_failed asset_id=%s", asset_id, exc_info=True)
        record_audio_delivery(channel="telegram", cue_type=cue_type, status="failed")
        return False


async def deliver_flip_committed_command(
    msg: Message,
    *,
    stake_tokens: int,
    outcome: str,
    balance_line: str,
    idempotent_replay: bool,
) -> None:
    pres = build_flip_presentation(
        stake_tokens=stake_tokens,
        outcome=outcome,
        balance_line=balance_line,
        idempotent_replay=idempotent_replay,
    )
    body = pres.steps[0].text or ""
    await msg.reply_text(body)


async def deliver_flip_committed_callback(
    query: CallbackQuery,
    *,
    stake_tokens: int,
    outcome: str,
    balance_line: str,
    idempotent_replay: bool,
) -> None:
    pres = build_flip_presentation(
        stake_tokens=stake_tokens,
        outcome=outcome,
        balance_line=balance_line,
        idempotent_replay=idempotent_replay,
    )
    body = pres.steps[0].text or ""
    try:
        await query.edit_message_text(body)
    except BadRequest:
        await query.message.reply_text(body)


async def deliver_wheel_committed_command(
    msg: Message,
    *,
    stake_tokens: int,
    outcome: str,
    payout_delta: float,
    balance_line: str,
    idempotent_replay: bool,
) -> None:
    pres = build_wheel_presentation(
        stake_tokens=stake_tokens,
        outcome=outcome,
        payout_delta=payout_delta,
        balance_line=balance_line,
        idempotent_replay=idempotent_replay,
    )
    any_voice_issue = False
    for step in pres.steps:
        if step.audio is not None:
            ok = await _send_voice_for_cue(
                msg,
                asset_id=step.audio.asset_id,
                cue_type=step.audio.cue_type,
            )
            if not ok:
                any_voice_issue = True
        if step.text:
            await msg.reply_text(step.text)
    if any_voice_issue:
        await msg.reply_text(game_texts.wheel_audio_sequence_fallback_notice())


async def deliver_wheel_committed_callback(
    query: CallbackQuery,
    *,
    stake_tokens: int,
    outcome: str,
    payout_delta: float,
    balance_line: str,
    idempotent_replay: bool,
) -> None:
    pres = build_wheel_presentation(
        stake_tokens=stake_tokens,
        outcome=outcome,
        payout_delta=payout_delta,
        balance_line=balance_line,
        idempotent_replay=idempotent_replay,
    )
    anchor = query.message
    assert anchor is not None
    any_voice_issue = False
    for idx, step in enumerate(pres.steps):
        if step.audio is not None:
            ok = await _send_voice_for_cue(
                anchor,
                asset_id=step.audio.asset_id,
                cue_type=step.audio.cue_type,
            )
            if not ok:
                any_voice_issue = True
        if step.text:
            body = step.text
            if idx == 1:
                try:
                    await query.edit_message_text(body)
                except BadRequest:
                    await anchor.reply_text(body)
            else:
                await anchor.reply_text(body)
    if any_voice_issue:
        await anchor.reply_text(game_texts.wheel_audio_sequence_fallback_notice())
