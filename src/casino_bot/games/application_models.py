"""Channel-agnostic game delivery types (Phase 6 — no Telegram / PTB imports)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Union

CueType = Literal["anticipation", "win", "lose"]


@dataclass(frozen=True)
class AudioCue:
    """Logical audio asset reference; channel adapter maps ``asset_id`` to bytes/path."""

    cue_type: CueType
    asset_id: str


@dataclass(frozen=True)
class PresentationStep:
    """One ordered slice of the UX: optional voice, optional text (after or without voice)."""

    text: str | None
    audio: AudioCue | None


@dataclass(frozen=True)
class GamePresentation:
    """User-facing ordered presentation (text + optional audio cues)."""

    steps: tuple[PresentationStep, ...]


@dataclass(frozen=True)
class SendPlainText:
    text: str


@dataclass(frozen=True)
class SendVoiceFromAsset:
    """Adapter resolves ``asset_id`` to a voice file or fallback."""

    asset_id: str
    cue_type: CueType


BotAction = Union[SendPlainText, SendVoiceFromAsset]


@dataclass(frozen=True)
class GameCommandResult:
    """Outcome of one game command for adapters/metrics (no ORM objects)."""

    game_id: str
    bet_amount: int
    idempotent_replay: bool
    round_status: str | None
    details: dict[str, Any] | None
    rejection_code: str | None = None
    cooldown_remaining_seconds: int | None = None
