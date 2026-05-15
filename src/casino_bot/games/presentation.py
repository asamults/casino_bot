"""Build channel-agnostic ``GamePresentation`` from round outcomes (Phase 6)."""

from __future__ import annotations

from casino_bot.games.application_models import (
    AudioCue,
    GamePresentation,
    PresentationStep,
)
from casino_bot.telegram_bot import game_texts


def build_flip_presentation(
    *,
    stake_tokens: int,
    outcome: str,
    balance_line: str,
    idempotent_replay: bool,
) -> GamePresentation:
    body = game_texts.flip_result_compact(
        stake_tokens=stake_tokens,
        outcome=outcome,
        balance_line=balance_line,
        idempotent_replay=idempotent_replay,
    )
    return GamePresentation(steps=(PresentationStep(text=body, audio=None),))


def build_wheel_presentation(
    *,
    stake_tokens: int,
    outcome: str,
    net_change_tokens: str,
    balance_line: str,
    idempotent_replay: bool,
) -> GamePresentation:
    """Anticipation audio → result text → win/lose audio (6C)."""
    result_body = game_texts.wheel_result_compact(
        stake_tokens=stake_tokens,
        outcome=outcome,
        net_change_tokens=net_change_tokens,
        balance_line=balance_line,
        idempotent_replay=idempotent_replay,
    )
    bust = outcome == "bust"
    outcome_cue: AudioCue = (
        AudioCue(cue_type="lose", asset_id="wheel_lose")
        if bust
        else AudioCue(cue_type="win", asset_id="wheel_win")
    )
    return GamePresentation(
        steps=(
            PresentationStep(
                text=None,
                audio=AudioCue(cue_type="anticipation", asset_id="wheel_anticipation"),
            ),
            PresentationStep(text=result_body, audio=None),
            PresentationStep(text=None, audio=outcome_cue),
        )
    )
