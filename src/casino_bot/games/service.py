"""API-agnostic game engine entrypoint (Phase 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from casino_bot.db.models import GameRound
from casino_bot.games import registry as game_registry
from casino_bot.games.rng import new_rng
from casino_bot.games.types import GameInput
from casino_bot.services.game_round_service import execute_game_round


class GameEngineRejected(Exception):
    """Validation / policy rejection before a round is persisted."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def run_game(
    db: Session,
    *,
    user_id: int,
    game_id: str,
    bet_amount: int,
    idempotency_key: str,
    actor: str = "game_engine",
) -> GameRound:
    """Run one enabled game round; idempotent by ``(user_id, game_id, idempotency_key)``.

    Balance changes only inside ``execute_game_round`` (Phase 1 ledger).
    """
    from casino_bot.settings import settings as app_settings

    if game_id not in app_settings.GAMES_ENABLED:
        raise GameEngineRejected("game_disabled", f"Game not enabled: {game_id!r}")

    if game_id == "coin_flip":
        if bet_amount < app_settings.COIN_FLIP_MIN_BET:
            raise GameEngineRejected(
                "bet_below_min",
                f"Bet {bet_amount} below minimum {app_settings.COIN_FLIP_MIN_BET}",
            )
        if bet_amount > app_settings.COIN_FLIP_MAX_BET:
            raise GameEngineRejected(
                "bet_above_max",
                f"Bet {bet_amount} above maximum {app_settings.COIN_FLIP_MAX_BET}",
            )
        if app_settings.COIN_FLIP_COOLDOWN_SECONDS > 0:
            last = (
                db.query(GameRound)
                .filter(
                    GameRound.user_id == user_id,
                    GameRound.game_id == game_id,
                    GameRound.status == "committed",
                    GameRound.committed_at.isnot(None),
                )
                .order_by(desc(GameRound.committed_at))
                .first()
            )
            if last is not None and last.committed_at is not None:
                elapsed = (_utcnow() - last.committed_at).total_seconds()
                if elapsed < app_settings.COIN_FLIP_COOLDOWN_SECONDS:
                    raise GameEngineRejected(
                        "cooldown_active",
                        "Coin flip cooldown not elapsed",
                    )

    existing = (
        db.query(GameRound)
        .filter(
            GameRound.user_id == user_id,
            GameRound.game_id == game_id,
            GameRound.idempotency_key == idempotency_key,
        )
        .first()
    )
    if existing is not None:
        return existing

    try:
        game = game_registry.get(game_id)
    except KeyError as exc:
        raise GameEngineRejected(
            "unknown_game", f"Game not registered: {game_id!r}"
        ) from exc

    rng = new_rng()
    inp = GameInput(
        user_id=user_id,
        bet_amount=bet_amount,
        idempotency_key=idempotency_key,
        client_context=None,
    )
    result = game.compute_outcome(inp, rng)
    details: dict[str, Any] = dict(result.details)
    return execute_game_round(
        db,
        user_id=user_id,
        game_id=game_id,
        idempotency_key=idempotency_key,
        bet_amount=float(bet_amount),
        actor=actor,
        details=details,
        payout_delta=result.payout_delta,
    )
