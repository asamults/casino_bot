"""Phase 7 — integer token_units ledger and game economics."""

from __future__ import annotations

import pytest

from casino_bot.db.models import LedgerEntry, TokenAccount
from casino_bot.games.bonus_wheel import BonusWheelGame
from casino_bot.games.service import GameEngineRejected, run_game
from casino_bot.games.types import GameInput
from casino_bot.services.economy_service import adjust_user_tokens
from casino_bot.services.token_amounts import (
    parse_whole_tokens_to_units,
    tokens_whole_to_units,
    validate_units,
)
from casino_bot.settings import Settings
from casino_bot.telegram_bot.user_ops import ensure_telegram_user


def _fund(db, *, user_id: int, whole_tokens: int, scale: int = 1000) -> None:
    adjust_user_tokens(
        db,
        user_id=user_id,
        delta_units=tokens_whole_to_units(whole_tokens, scale=scale),
        reason="test:fund",
        actor="tests",
    )


class _FakeRng:
    def __init__(self, value: float) -> None:
        self._value = value

    def random(self) -> float:
        return self._value


def test_package_sizes_convert_to_exact_units() -> None:
    s = 1000
    assert tokens_whole_to_units(100, scale=s) == 100_000
    assert tokens_whole_to_units(1000, scale=s) == 1_000_000
    assert tokens_whole_to_units(10000, scale=s) == 10_000_000


def test_validate_units_rejects_bool() -> None:
    with pytest.raises(TypeError):
        validate_units(True, name="x")


def test_access_gate_uses_units(
    monkeypatch: pytest.MonkeyPatch, sqlite_session
) -> None:
    cfg = Settings(
        _env_file=None,
        GAMES_ENABLED=["coin_flip"],
        GAME_ACCESS_MIN_TOKENS=2,
        TOKEN_UNIT_SCALE=1000,
    )
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    user = ensure_telegram_user(sqlite_session, telegram_user_id=97001)
    _fund(sqlite_session, user_id=user.id, whole_tokens=1, scale=1000)
    sqlite_session.commit()
    with pytest.raises(GameEngineRejected) as ei:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=1,
            idempotency_key="p7-gate",
            actor="tests",
        )
    assert ei.value.code == "access_tokens_required"


def test_coin_flip_stake_is_integer_units(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.99))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=97002)
    _fund(sqlite_session, user_id=user.id, whole_tokens=50)
    sqlite_session.commit()
    gr = run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=7,
        idempotency_key="p7-stake",
        actor="tests",
    )
    sqlite_session.commit()
    assert gr.bet_units == 7_000
    assert gr.payout_units == -7_000


def test_bonus_wheel_payout_deterministic_units() -> None:
    g = BonusWheelGame()
    rng = _FakeRng(0.60)
    inp = GameInput(
        user_id=1,
        bet_amount=10,
        idempotency_key="x",
        client_context=None,
    )
    res = g.compute_outcome(inp, rng)  # type: ignore[arg-type]
    assert res.details["outcome"] == "bronze"
    assert res.payout_delta_units == 5_000


def test_ledger_sum_matches_balance_after_rounds(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=97003)
    _fund(sqlite_session, user_id=user.id, whole_tokens=100)
    sqlite_session.commit()
    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=10,
        idempotency_key="a",
        actor="tests",
    )
    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=5,
        idempotency_key="b",
        actor="tests",
    )
    sqlite_session.commit()
    acc = (
        sqlite_session.query(TokenAccount).filter(TokenAccount.user_id == user.id).one()
    )
    ledger_sum = sum(
        int(r.delta_units)
        for r in sqlite_session.query(LedgerEntry)
        .filter(LedgerEntry.user_id == user.id)
        .all()
    )
    assert ledger_sum == acc.balance_units


def test_idempotency_no_double_units(sqlite_session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=97004)
    _fund(sqlite_session, user_id=user.id, whole_tokens=20)
    sqlite_session.commit()
    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=1,
        idempotency_key="idem-p7",
        actor="tests",
    )
    sqlite_session.commit()
    b1 = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=1,
        idempotency_key="idem-p7",
        actor="tests",
    )
    sqlite_session.commit()
    b2 = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    assert b1 == b2


def test_parse_whole_tokens_rejects_fractional_string() -> None:
    with pytest.raises(ValueError, match="whole"):
        parse_whole_tokens_to_units("10.5", scale=1000)
