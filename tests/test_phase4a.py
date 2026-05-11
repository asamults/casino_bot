"""Phase 4A — cooldown UX, settings, Telegram rate limits, /rounds scoping."""

from __future__ import annotations

import pytest

from casino_bot.games.service import run_game
from casino_bot.settings import Settings

from casino_bot.telegram_bot import game_texts
from casino_bot.telegram_bot.handlers import rounds_history_message
from casino_bot.telegram_bot.rate_limit import (
    allow_flip_action,
    allow_flip_prompt,
    reset_telegram_rate_limiters_for_tests,
)
from casino_bot.telegram_bot.user_ops import ensure_telegram_user
from casino_bot.services.economy_service import adjust_user_tokens


def _minimal_production_settings(**kwargs: object) -> Settings:
    merged: dict[str, object] = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "p" * 32,
        "DATABASE_URL": "postgresql+psycopg://u:p@db.prod.example.com:5432/db",
        "JWT_SIGNING_KEY": "j" * 32,
        "REFRESH_TOKEN_PEPPER": "r" * 32,
        "USER_API_INTERNAL_TOKEN": "i" * 32,
        "CORS_ALLOW_ORIGINS": ["https://admin.example.com"],
        "ALLOWED_HOSTS": ["api.example.com"],
        "BILLING_ALLOWED_RETURN_HOSTS": ["admin.example.com"],
    }
    merged.update(kwargs)
    return Settings(_env_file=None, **merged)


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


def test_effective_cooldown_production_defaults_when_zero() -> None:
    s = _minimal_production_settings(
        COIN_FLIP_COOLDOWN_SECONDS=0,
        COIN_FLIP_ALLOW_ZERO_COOLDOWN_IN_PRODUCTION=False,
    )
    assert s.effective_coin_flip_cooldown_seconds() == 3


def test_effective_cooldown_production_respects_explicit_nonzero() -> None:
    s = _minimal_production_settings(COIN_FLIP_COOLDOWN_SECONDS=7)
    assert s.effective_coin_flip_cooldown_seconds() == 7


def test_effective_cooldown_production_zero_when_opted_in() -> None:
    s = _minimal_production_settings(
        COIN_FLIP_COOLDOWN_SECONDS=0,
        COIN_FLIP_ALLOW_ZERO_COOLDOWN_IN_PRODUCTION=True,
    )
    assert s.effective_coin_flip_cooldown_seconds() == 0


def test_effective_cooldown_development_uses_raw() -> None:
    s = Settings(
        _env_file=None, ENVIRONMENT="development", COIN_FLIP_COOLDOWN_SECONDS=0
    )
    assert s.effective_coin_flip_cooldown_seconds() == 0


def test_game_engine_rejected_user_message_cooldown_seconds() -> None:
    body = game_texts.game_engine_rejected_user_message(
        "cooldown_active",
        cooldown_remaining_seconds=12,
    )
    assert "12" in body
    assert "second" in body.lower()


def test_flip_prompt_rate_limit_window(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = Settings(_env_file=None, TELEGRAM_FLIP_PROMPT_RATE_LIMIT_PER_MINUTE=3)
    monkeypatch.setattr("casino_bot.telegram_bot.rate_limit.settings", cfg)
    reset_telegram_rate_limiters_for_tests()
    tid = 990010203
    assert allow_flip_prompt(tid)
    assert allow_flip_prompt(tid)
    assert allow_flip_prompt(tid)
    assert not allow_flip_prompt(tid)


def test_flip_action_rate_limit_window(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = Settings(_env_file=None, TELEGRAM_FLIP_ACTION_RATE_LIMIT_PER_MINUTE=2)
    monkeypatch.setattr("casino_bot.telegram_bot.rate_limit.settings", cfg)
    reset_telegram_rate_limiters_for_tests()
    tid = 990010204
    assert allow_flip_action(tid)
    assert allow_flip_action(tid)
    assert not allow_flip_action(tid)


def test_rounds_history_scoped_to_internal_user(
    sqlite_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("casino_bot.games.service.new_rng", lambda: _FakeRng(0.99))
    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip"])
    monkeypatch.setattr("casino_bot.settings.settings", cfg)
    monkeypatch.setattr("casino_bot.telegram_bot.handlers.settings", cfg)
    u1 = ensure_telegram_user(sqlite_session, telegram_user_id=88001)
    u2 = ensure_telegram_user(sqlite_session, telegram_user_id=88002)
    _fund(sqlite_session, user_id=u1.id, amount=100.0)
    _fund(sqlite_session, user_id=u2.id, amount=100.0)
    sqlite_session.commit()
    run_game(
        sqlite_session,
        user_id=u1.id,
        game_id="coin_flip",
        bet_amount=2,
        idempotency_key="u1-a",
        actor="tests",
    )
    sqlite_session.commit()
    run_game(
        sqlite_session,
        user_id=u2.id,
        game_id="coin_flip",
        bet_amount=3,
        idempotency_key="u2-a",
        actor="tests",
    )
    sqlite_session.commit()
    out1 = rounds_history_message(sqlite_session, user_id=u1.id)
    out2 = rounds_history_message(sqlite_session, user_id=u2.id)
    assert "bet=2" in out1
    assert "bet=3" not in out1
    assert "bet=3" in out2
    assert "bet=2" not in out2
