"""Phase 2 game engine: registry, coin_flip, round ledger integration."""

from __future__ import annotations

import secrets
from unittest.mock import patch

import pytest

from casino_bot.db.models import GameRound, TokenAccount
from casino_bot.games.registry import list_games
from casino_bot.games.service import GameEngineRejected, run_game
from casino_bot.services.economy_service import adjust_user_tokens
from casino_bot.services.token_amounts import tokens_whole_to_units
from casino_bot.settings import Settings
from casino_bot.telegram_bot.user_ops import ensure_telegram_user


def _fund(db, *, user_id: int, whole_tokens: int) -> None:
    from casino_bot.settings import settings as app_settings

    adjust_user_tokens(
        db,
        user_id=user_id,
        delta_units=tokens_whole_to_units(
            whole_tokens, scale=app_settings.TOKEN_UNIT_SCALE
        ),
        reason="test:fund",
        actor="tests",
    )


class _FakeRng:
    def __init__(self, value: float) -> None:
        self._value = value

    def random(self) -> float:
        return self._value


def test_registry_lists_enabled_games(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip"])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    ids = [g.game_id for g in list_games()]
    assert ids == ["coin_flip"]

    cfg2 = Settings(_env_file=None, GAMES_ENABLED=[])
    monkeypatch.setattr("casino_bot.settings.settings", cfg2)
    assert list_games() == []


def test_coin_flip_win_credits_plus_bet(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92001)
    _fund(sqlite_session, user_id=user.id, whole_tokens=100)
    sqlite_session.commit()

    gr = run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=10,
        idempotency_key="win-1",
        actor="tests",
    )
    sqlite_session.commit()

    assert gr.status == "committed"
    assert gr.payout_units == 10_000
    bal = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    assert bal == 110_000
    d = gr.details_json or {}
    assert d["outcome"] == "win"
    assert d["payout_delta_units"] == 10_000
    assert d["prize"] == 10
    assert d["rng_version"] == "v1"
    assert d["game"] == "coin_flip"


def test_coin_flip_lose_debits_minus_bet(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.99))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92002)
    _fund(sqlite_session, user_id=user.id, whole_tokens=100)
    sqlite_session.commit()

    gr = run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=10,
        idempotency_key="lose-1",
        actor="tests",
    )
    sqlite_session.commit()

    assert gr.status == "committed"
    assert gr.payout_units == -10_000
    bal = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    assert bal == 90_000
    d = gr.details_json or {}
    assert d["outcome"] == "lose"
    assert d["payout_delta_units"] == -10_000
    assert d["prize"] == 0


def test_idempotency_key_replay_same_round_no_double_spend(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92003)
    _fund(sqlite_session, user_id=user.id, whole_tokens=100)
    sqlite_session.commit()

    gr1 = run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=10,
        idempotency_key="idem-1",
        actor="tests",
    )
    sqlite_session.commit()
    # Second call would "lose" if RNG ran again — must not re-roll.
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.99))
    gr2 = run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=10,
        idempotency_key="idem-1",
        actor="tests",
    )
    sqlite_session.commit()

    assert gr1.id == gr2.id
    assert (gr1.details_json or {}).get("outcome") == "win"
    assert (gr2.details_json or {}).get("outcome") == "win"
    bal = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    assert bal == 110_000


def test_disabled_game_rejected(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = Settings(_env_file=None, GAMES_ENABLED=[])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92004)
    _fund(sqlite_session, user_id=user.id, whole_tokens=50)
    sqlite_session.commit()

    with pytest.raises(GameEngineRejected) as excinfo:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=5,
            idempotency_key="x",
            actor="tests",
        )
    assert excinfo.value.code == "game_disabled"
    n = sqlite_session.query(GameRound).filter(GameRound.user_id == user.id).count()
    assert n == 0


def test_below_min_bet_rejected(sqlite_session) -> None:
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92005)
    _fund(sqlite_session, user_id=user.id, whole_tokens=50)
    sqlite_session.commit()

    with pytest.raises(GameEngineRejected) as excinfo:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=0,
            idempotency_key="min",
            actor="tests",
        )
    assert excinfo.value.code == "bet_below_min"


def test_above_max_bet_rejected(sqlite_session) -> None:
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92006)
    _fund(sqlite_session, user_id=user.id, whole_tokens=200)
    sqlite_session.commit()

    with pytest.raises(GameEngineRejected) as excinfo:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=101,
            idempotency_key="max",
            actor="tests",
        )
    assert excinfo.value.code == "bet_above_max"


def test_insufficient_funds_rejected(sqlite_session, monkeypatch: pytest.MonkeyPatch):
    """Stake must be covered up front (even if RNG would have yielded a win)."""
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.99))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92007)
    _fund(sqlite_session, user_id=user.id, whole_tokens=3)
    sqlite_session.commit()

    with pytest.raises(GameEngineRejected) as excinfo:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=10,
            idempotency_key="poor",
            actor="tests",
        )
    assert excinfo.value.code == "insufficient_balance"

    bal = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    assert bal == 3_000


def test_insufficient_balance_blocks_win_outcome(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92010)
    _fund(sqlite_session, user_id=user.id, whole_tokens=7)
    sqlite_session.commit()

    with pytest.raises(GameEngineRejected) as excinfo:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=10,
            idempotency_key="cant-cover-10",
            actor="tests",
        )
    assert excinfo.value.code == "insufficient_balance"
    bal = (
        sqlite_session.query(TokenAccount)
        .filter(TokenAccount.user_id == user.id)
        .one()
        .balance_units
    )
    assert bal == 7_000


def test_idempotent_replay_skips_cooldown(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
):
    cfg = Settings(
        _env_file=None,
        GAMES_ENABLED=["coin_flip"],
        COIN_FLIP_COOLDOWN_SECONDS=3600,
    )
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92011)
    _fund(sqlite_session, user_id=user.id, whole_tokens=100)
    sqlite_session.commit()

    gr1 = run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=1,
        idempotency_key="same-key",
        actor="tests",
    )
    sqlite_session.commit()
    gr2 = run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=1,
        idempotency_key="same-key",
        actor="tests",
    )
    sqlite_session.commit()
    assert gr1.id == gr2.id


def test_cooldown_blocks_new_idempotency_key(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
):
    cfg = Settings(
        _env_file=None,
        GAMES_ENABLED=["coin_flip"],
        COIN_FLIP_COOLDOWN_SECONDS=3600,
    )
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92012)
    _fund(sqlite_session, user_id=user.id, whole_tokens=100)
    sqlite_session.commit()

    run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=1,
        idempotency_key="first",
        actor="tests",
    )
    sqlite_session.commit()

    with pytest.raises(GameEngineRejected) as excinfo:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id="coin_flip",
            bet_amount=1,
            idempotency_key="second",
            actor="tests",
        )
    assert excinfo.value.code == "cooldown_active"
    assert excinfo.value.cooldown_remaining_seconds is not None


def test_coin_flip_win_rate_sanity_200_flips(sqlite_session) -> None:
    """Obvious RNG bugs (e.g. always lose) should fail this band."""
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92008)
    _fund(sqlite_session, user_id=user.id, whole_tokens=10_000)
    sqlite_session.commit()

    wins = 0
    with patch(
        "casino_bot.games.service.new_rng",
        side_effect=lambda: secrets.SystemRandom(),
    ):
        for i in range(200):
            gr = run_game(
                sqlite_session,
                user_id=user.id,
                game_id="coin_flip",
                bet_amount=1,
                idempotency_key=f"stat-{i}",
                actor="tests",
            )
            sqlite_session.commit()
            assert gr.status == "committed"
            if (gr.details_json or {}).get("outcome") == "win":
                wins += 1

    assert 30 <= wins <= 170


def test_default_actor_game_engine(sqlite_session, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    user = ensure_telegram_user(sqlite_session, telegram_user_id=92009)
    _fund(sqlite_session, user_id=user.id, whole_tokens=10)
    sqlite_session.commit()

    gr = run_game(
        sqlite_session,
        user_id=user.id,
        game_id="coin_flip",
        bet_amount=1,
        idempotency_key="actor-default",
    )
    sqlite_session.commit()
    assert gr.status == "committed"
