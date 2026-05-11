from __future__ import annotations

import logging
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from casino_bot.compliance.violations import ComplianceViolation
from casino_bot.db.models import GameRound
from casino_bot.services import economy_service
from casino_bot.services.audit_service import audit_log

_log = logging.getLogger("casino_bot.game_rounds")

# Phase 1 limits: keep simple and explicit.
MAX_BET_AMOUNT = 10_000.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def execute_game_round(
    db: Session,
    *,
    user_id: int,
    game_id: str,
    idempotency_key: str,
    bet_amount: float,
    actor: str,
    details: dict[str, Any] | None = None,
    payout_delta: float | None = None,
) -> GameRound:
    """Execute one game round atomically with the token ledger.

    Idempotency scope is (user_id, game_id, idempotency_key).

    If ``payout_delta`` is None (Phase 1 default), the ledger delta is ``-bet_amount``
    (stake debit only). If set (Phase 2+), that value is applied instead.
    """

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

    if bet_amount is None or not isinstance(bet_amount, (int, float)):
        raise ValueError("bet_amount must be a number")
    if math.isnan(float(bet_amount)) or not math.isfinite(float(bet_amount)):
        raise ValueError("bet_amount must be finite")
    if float(bet_amount) <= 0:
        raise ValueError("bet_amount must be > 0")
    if float(bet_amount) > MAX_BET_AMOUNT:
        raise ValueError("bet_amount exceeds Phase 1 maximum")

    round_id = str(uuid.uuid4())
    if payout_delta is None:
        attempted_delta = -float(bet_amount)  # Phase 1: stake debit only.
    else:
        if math.isnan(float(payout_delta)) or not math.isfinite(float(payout_delta)):
            raise ValueError("payout_delta must be finite")
        attempted_delta = float(payout_delta)
    reason = f"game_round:{game_id}:{round_id}"

    try:
        tx_ctx = db.begin_nested() if db.in_transaction() else db.begin()
        with tx_ctx:
            # Get-or-create via unique constraint; insert early to lock the key.
            gr = GameRound(
                round_id=round_id,
                user_id=user_id,
                game_id=game_id,
                idempotency_key=idempotency_key,
                bet_amount=float(bet_amount),
                payout_delta=attempted_delta,
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
                    delta=attempted_delta,
                    reason=reason,
                    actor=actor,
                )
            except ComplianceViolation as exc:
                # Explicit rejected record, no balance mutation.
                gr.status = "rejected"
                gr.payout_delta = 0.0
                gr.details_json = {
                    **(details or {}),
                    "rejection_reason": str(exc),
                    "attempted_delta": attempted_delta,
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
                        "bet_amount": float(bet_amount),
                        "attempted_delta": attempted_delta,
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
                "game_round_result round_id=%s user_id=%s game_id=%s status=%s delta=%s",
                round_id,
                user_id,
                game_id,
                gr.status,
                attempted_delta,
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
                    round_id=round_id,
                    user_id=user_id,
                    game_id=game_id,
                    idempotency_key=idempotency_key,
                    bet_amount=float(bet_amount),
                    payout_delta=0.0,
                    status="failed",
                    details_json={
                        **(details or {}),
                        "attempted_delta": attempted_delta,
                        "error_class": exc.__class__.__name__,
                    },
                    committed_at=None,
                )
                db.add(failed)
        except IntegrityError:
            db.rollback()
        _log.exception(
            "game_round_failed round_id=%s user_id=%s game_id=%s",
            round_id,
            user_id,
            game_id,
            exc_info=exc,
        )
        raise
