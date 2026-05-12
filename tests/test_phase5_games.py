"""Phase 5 — multi-game catalog, bonus wheel engine, Telegram catalog text."""

from __future__ import annotations

import pytest

from casino_bot.games.bonus_wheel import BONUS_WHEEL_GAME_ID
from casino_bot.games.registry import list_enabled_games, list_games
from casino_bot.games.service import GameEngineRejected, run_game
from casino_bot.services.economy_service import adjust_user_tokens
from casino_bot.settings import Settings
from casino_bot.telegram_bot import game_texts
from casino_bot.telegram_bot.user_ops import ensure_telegram_user


def _fund(db, *, user_id: int, amount: float) -> None:
    adjust_user_tokens(
        db,
        user_id=user_id,
        delta=amount,
        reason="test:fund",
        actor="tests",
    )


class _FakeRng:
    def __init__(self, value: float) -> None:
        self._value = value

    def random(self) -> float:
        return self._value


def test_list_enabled_games_respects_games_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip", BONUS_WHEEL_GAME_ID])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    metas = list_enabled_games()
    assert [m.game_id for m in metas] == ["bonus_wheel", "coin_flip"]
    assert all(m.min_bet >= 1 and m.max_bet >= m.min_bet for m in metas)

    cfg2 = Settings(_env_file=None, GAMES_ENABLED=[BONUS_WHEEL_GAME_ID])
    monkeypatch.setattr("casino_bot.settings.settings", cfg2)
    assert [g.game_id for g in list_games()] == [BONUS_WHEEL_GAME_ID]
    metas2 = list_enabled_games()
    assert len(metas2) == 1
    assert metas2[0].game_id == BONUS_WHEEL_GAME_ID


def test_bonus_wheel_bust_path(sqlite_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.0))
    cfg = Settings(_env_file=None, GAMES_ENABLED=[BONUS_WHEEL_GAME_ID])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    user = ensure_telegram_user(sqlite_session, telegram_user_id=94001)
    _fund(sqlite_session, user_id=user.id, amount=50.0)
    sqlite_session.commit()

    gr = run_game(
        sqlite_session,
        user_id=user.id,
        game_id=BONUS_WHEEL_GAME_ID,
        bet_amount=10,
        idempotency_key="bw-1",
        actor="tests",
    )
    sqlite_session.commit()
    assert gr.status == "committed"
    d = gr.details_json or {}
    assert d["outcome"] == "bust"
    assert gr.payout_delta == -10.0


def test_bonus_wheel_rejects_below_min(sqlite_session, monkeypatch: pytest.MonkeyPatch):
    cfg = Settings(_env_file=None, GAMES_ENABLED=[BONUS_WHEEL_GAME_ID])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    user = ensure_telegram_user(sqlite_session, telegram_user_id=94002)
    _fund(sqlite_session, user_id=user.id, amount=50.0)
    sqlite_session.commit()
    with pytest.raises(GameEngineRejected) as ei:
        run_game(
            sqlite_session,
            user_id=user.id,
            game_id=BONUS_WHEEL_GAME_ID,
            bet_amount=0,
            idempotency_key="x",
            actor="tests",
        )
    assert ei.value.code == "bet_below_min"


def test_games_catalog_message_lists_two_games(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip", BONUS_WHEEL_GAME_ID])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    body = game_texts.games_catalog_message(list_enabled_games())
    assert "Coin flip" in body
    assert "Bonus wheel" in body
    assert "/flip" in body and "/wheel" in body
