"""Game engine types (Phase 2)."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class GameInput:
    """Immutable input for one game resolution (no balance side effects)."""

    user_id: int
    bet_amount: int
    idempotency_key: str
    client_context: dict[str, Any] | None = None


@dataclass(frozen=True)
class GameResult:
    """Outcome of ``compute_outcome``; balance is applied only via round ledger."""

    outcome: str
    payout_delta: float
    prize: int
    details: dict[str, Any]


@runtime_checkable
class Game(Protocol):
    """Plugin contract: one game id + deterministic outcome from RNG."""

    @property
    def game_id(self) -> str: ...

    def compute_outcome(
        self, inp: GameInput, rng: secrets.SystemRandom
    ) -> GameResult: ...
