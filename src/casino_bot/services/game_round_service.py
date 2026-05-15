from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from casino_bot.compliance.violations import ComplianceViolation
from casino_bot.db.models import GameRound
from casino_bot.services import economy_service, token_amounts
from casino_bot.services.audit_service import audit_log

_log = logging.getLogger("casino_bot.game_rounds")

# Phase 1 limits: whole visible tokens per round.
MAX_BET_AMOUNT = 10_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def execute_game_round(
    db: Session,
    *,
    user_id: int,
    game_id: str,
    idempotency_key: str,
    bet_amount: int,
    actor: str,
    details: dict[str, Any] | None = None,
    payout_delta_units: int | None = None,
) -> GameRound:
    """Execute one game round atomically with the token ledger (integer units).

    Idempotency scope is (user_id, game_id, idempotency_key).

    If ``payout_delta_units`` is None (Phase 1 default), the ledger delta is ``-bet_units``
    (stake debit only). If set (Phase 2+), that signed unit amount is applied instead.
    """
    from casino_bot.settings import settings as app_settings

    scale = app_settings.TOKEN_UNIT_SCALE

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

    if not isinstance(bet_amount, int) or isinstance(bet_amount, bool):
        raise ValueError("bet_amount must be an int (whole visible tokens)")
    if bet_amount <= 0:
        raise ValueError("bet_amount must be > 0")
    if bet_amount > MAX_BET_AMOUNT:
        raise ValueError("bet_amount exceeds Phase 1 maximum")

    bet_units = token_amounts.tokens_whole_to_units(bet_amount, scale=scale)

    if payout_delta_units is None:
        attempted_delta_units = -bet_units
    else:
        token_amounts.validate_units(payout_delta_units, name="payout_delta_units")
        attempted_delta_units = payout_delta_units

    attempted_delta_float = token_amounts.units_to_storage_float(
        attempted_delta_units, scale=scale
    )
    bet_float = token_amounts.units_to_storage_float(bet_units, scale=scale)

    try:
        tx_ctx = db.begin_nested() if db.in_transaction() else db.begin()
        with tx_ctx:
            round_id = str(uuid.uuid4())
            reason = f"game_round:{game_id}:{round_id}"
            gr = GameRound(
                round_id=round_id,
                user_id=user_id,
                game_id=game_id,
                idempotency_key=idempotency_key,
                bet_amount=bet_float,
                bet_units=bet_units,
                payout_delta=attempted_delta_float,
                payout_units=attempted_delta_units,
                status="failed",  # will be set to committed/rejected before commit
                details_json=(details or None),
                committed_at=None,
            )
            db.add(gr)
            db.flush()

            try:
                economy_service.adjust_user_tokens(
                    db,
                    user_id=user_id,
                    delta_units=attempted_delta_units,
                    reason=reason,
                    actor=actor,
                )
            except ComplianceViolation as exc:
                # Explicit rejected record, no balance mutation.
                gr.status = "rejected"
                gr.payout_delta = 0.0
                gr.payout_units = 0
                gr.details_json = {
                    **(details or {}),
                    "rejection_reason": str(exc),
                    "attempted_delta_units": attempted_delta_units,
                }
                audit_log(
                    db,
                    actor=actor,
                    action="game_round_rejected",
                    details={
                        "user_id": user_id,
                        "game_id": game_id,
                        "round_id": round_id,
                        "idempotency_key": idempotency_key,
                        "bet_amount": bet_amount,
                        "attempted_delta_units": attempted_delta_units,
                        "reason": reason,
                        "error": str(exc),
                    },
                )
                _log.info(
                    "game_round_result round_id=%s user_id=%s game_id=%s status=%s",
                    round_id,
                    user_id,
                    game_id,
                    gr.status,
                )
                return gr

            gr.status = "committed"
            gr.committed_at = _utcnow()
            _log.info(
                "game_round_result round_id=%s user_id=%s game_id=%s status=%s delta_units=%s",
                round_id,
                user_id,
                game_id,
                gr.status,
                attempted_delta_units,
            )
            return gr
    except IntegrityError:
        db.rollback()
        # Another concurrent transaction inserted the same idempotency tuple.
        deadline = time.monotonic() + 0.5
        while True:
            gr = (
                db.query(GameRound)
                .filter(
                    GameRound.user_id == user_id,
                    GameRound.game_id == game_id,
                    GameRound.idempotency_key == idempotency_key,
                )
                .first()
            )
            if gr is not None:
                return gr
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.01)
    except Exception as exc:
        db.rollback()
        # Best-effort failed record (separate transaction) for investigations.
        try:
            with db.begin():
                failed = GameRound(
                    round_id=str(uuid.uuid4()),
                    user_id=user_id,
                    game_id=game_id,
                    idempotency_key=idempotency_key,
                    bet_amount=bet_float,
                    bet_units=bet_units,
                    payout_delta=0.0,
                    payout_units=0,
                    status="failed",
                    details_json={
                        **(details or {}),
                        "attempted_delta_units": attempted_delta_units,
                        "error_class": exc.__class__.__name__,
                    },
                    committed_at=None,
                )
                db.add(failed)
        except IntegrityError:
            db.rollback()
        _log.exception(
            "game_round_failed user_id=%s game_id=%s",
            user_id,
            game_id,
            exc_info=exc,
        )
        raise
