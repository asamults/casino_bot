"""Telegram bot unit tests (no Telegram network)."""

from __future__ import annotations

import pytest

from casino_bot.settings import Settings
from casino_bot.telegram_bot.preflight import telegram_polling_startup_error
from casino_bot.telegram_bot.texts import (
    BALANCE_UNAVAILABLE,
    welcome_message,
)
from casino_bot.telegram_bot.user_ops import (
    ensure_telegram_user,
    get_user_by_telegram_id,
    resolve_balance_reply,
)


def test_settings_allow_empty_telegram_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    cfg = Settings(_env_file=None)
    assert cfg.TELEGRAM_BOT_TOKEN == ""
    assert cfg.TELEGRAM_BOT_ENABLED is False


def test_preflight_reports_missing_token() -> None:
    cfg = Settings(
        _env_file=None,
        TELEGRAM_BOT_ENABLED=True,
        TELEGRAM_BOT_TOKEN="",
        TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS=["development"],
        ENVIRONMENT="development",
    )
    err = telegram_polling_startup_error(cfg)
    assert err is not None
    assert "TELEGRAM_BOT_TOKEN" in err


def test_preflight_rejects_doc_placeholder_token() -> None:
    cfg = Settings(
        _env_file=None,
        TELEGRAM_BOT_ENABLED=True,
        TELEGRAM_BOT_TOKEN="TOKEN_FROM_BOTFATHER",
        TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS=["development"],
        ENVIRONMENT="development",
    )
    err = telegram_polling_startup_error(cfg)
    assert err is not None
    assert "BotFather" in err


def test_preflight_blocks_production_with_default_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production is not in TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS by default."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db",
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("JWT_SIGNING_KEY", "y" * 32)
    monkeypatch.setenv("REFRESH_TOKEN_PEPPER", "z" * 32)
    monkeypatch.setenv(
        "USER_API_INTERNAL_TOKEN", "prod_user_api_internal_token_min_len_32_____"
    )
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://admin.example.com"]')
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com")
    monkeypatch.setenv("BILLING_ALLOWED_RETURN_HOSTS", "admin.example.com")
    monkeypatch.setenv("TELEGRAM_BOT_ENABLED", "true")
    monkeypatch.setenv(
        "TELEGRAM_BOT_TOKEN",
        "999999999:ABCDEF_TEST_TOKEN_NOT_SECRET_XXXXX",  # BotFather-shaped dummy
    )
    cfg = Settings(_env_file=None)
    err = telegram_polling_startup_error(cfg)
    assert err is not None
    assert "not allowed" in err.lower()


def test_telegram_polling_allowlist_splits_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS", "development,staging")
    cfg = Settings(_env_file=None)
    assert cfg.TELEGRAM_POLLING_ALLOWED_ENVIRONMENTS == ["development", "staging"]


def test_ensure_telegram_user_creates_and_reuses(sqlite_session) -> None:
    u1 = ensure_telegram_user(sqlite_session, telegram_user_id=88001)
    sqlite_session.commit()
    u2 = ensure_telegram_user(sqlite_session, telegram_user_id=88001)
    assert u1.id == u2.id
    assert get_user_by_telegram_id(sqlite_session, 88001) is not None


def test_welcome_message_shape() -> None:
    text = welcome_message(internal_user_id=42)
    assert "42" in text
    assert "Welcome" in text
    assert "/help" in text


def test_resolve_balance_reply_safe_without_token_account(sqlite_session) -> None:
    from casino_bot.db.models import User

    u = User(is_active=True, telegram_user_id=77001)
    sqlite_session.add(u)
    sqlite_session.commit()
    reply = resolve_balance_reply(sqlite_session, user_id=u.id)
    assert reply == BALANCE_UNAVAILABLE
