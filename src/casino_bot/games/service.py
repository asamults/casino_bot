"""API-agnostic game engine entrypoint (Phase 2)."""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from casino_bot.core.metrics import (
    record_game_engine_rejection,
    record_game_round_completion,
)
from casino_bot.db.models import GameRound, TokenAccount
from casino_bot.games import registry as game_registry
from casino_bot.games.rng import new_rng
from casino_bot.games.types import GameInput
from casino_bot.services.game_round_service import execute_game_round


class GameEngineRejected(Exception):
    """Validation / policy rejection before a round is persisted."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        cooldown_remaining_seconds: int | None = None,
    ) -> None:
        self.code = code
        self.cooldown_remaining_seconds = cooldown_remaining_seconds
        super().__init__(message or code)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _run_game_detailed_inner(
    db: Session,
    *,
    user_id: int,
    game_id: str,
    bet_amount: int,
    idempotency_key: str,
    actor: str = "game_engine",
) -> tuple[GameRound, bool]:
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
        return existing, True

    if game_id == "coin_flip":
        cooldown_sec = app_settings.effective_coin_flip_cooldown_seconds()
        if cooldown_sec > 0:
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
                elapsed = (_utcnow() - _as_utc_aware(last.committed_at)).total_seconds()
                if elapsed < cooldown_sec:
                    remaining = cooldown_sec - elapsed
                    secs = max(1, int(math.ceil(remaining)))
                    raise GameEngineRejected(
                        "cooldown_active",
                        "Coin flip cooldown not elapsed",
                        cooldown_remaining_seconds=secs,
                    )

        acc = db.query(TokenAccount).filter(TokenAccount.user_id == user_id).first()
        bal = float(acc.balance) if acc is not None else 0.0
        if bal + 1e-9 < float(bet_amount):
            raise GameEngineRejected(
                "insufficient_balance",
                f"Balance {bal} is below required stake {bet_amount}",
            )

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
    gr = execute_game_round(
        db,
        user_id=user_id,
        game_id=game_id,
        idempotency_key=idempotency_key,
        bet_amount=float(bet_amount),
        actor=actor,
        details=details,
        payout_delta=result.payout_delta,
    )
    return gr, False


def run_game_detailed(
    db: Session,
    *,
    user_id: int,
    game_id: str,
    bet_amount: int,
    idempotency_key: str,
    actor: str = "game_engine",
) -> tuple[GameRound, bool]:
    """Run one round; returns ``(round, idempotent_replay)``.

    Idempotency is keyed by ``(user_id, game_id, idempotency_key)``. When that row
    already exists, it is returned immediately with ``idempotent_replay=True`` —
    cooldown and stake/balance checks are skipped so duplicate Telegram deliveries
    replay the same persisted outcome (see Phase 4A idempotency docs).

    Prometheus metrics (Phase 4B) are recorded here — single entrypoint for gameplay.
    """
    start = time.perf_counter()
    try:
        gr, replay = _run_game_detailed_inner(
            db,
            user_id=user_id,
            game_id=game_id,
            bet_amount=bet_amount,
            idempotency_key=idempotency_key,
            actor=actor,
        )
    except GameEngineRejected as exc:
        record_game_engine_rejection(
            game_id=game_id,
            code=exc.code,
            duration_seconds=time.perf_counter() - start,
        )
        raise
    raw_details = gr.details_json
    details_dict = raw_details if isinstance(raw_details, dict) else None
    record_game_round_completion(
        game_id=game_id,
        status=str(gr.status),
        details=details_dict,
        bet_amount=float(gr.bet_amount),
        payout_delta=float(gr.payout_delta),
        idempotent_replay=replay,
        duration_seconds=time.perf_counter() - start,
    )
    return gr, replay


def run_game(
    db: Session,
    *,
    user_id: int,
    game_id: str,
    bet_amount: int,
    idempotency_key: str,
    actor: str = "game_engine",
) -> GameRound:
    """Run one enabled game round; idempotent by ``(user_id, game_id, idempotency_key)``."""
    gr, _ = run_game_detailed(
        db,
        user_id=user_id,
        game_id=game_id,
        bet_amount=bet_amount,
        idempotency_key=idempotency_key,
        actor=actor,
    )
    return gr
