"""Telegram bot unit tests (no Telegram network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from casino_bot.settings import Settings
from casino_bot.telegram_bot.handlers import database_ready_for_status
from casino_bot.telegram_bot.preflight import telegram_polling_startup_error
from casino_bot.telegram_bot.texts import (
    BALANCE_UNAVAILABLE,
    GENERIC_SUPPORT_LINE,
    admin_message,
    help_message,
    profile_message,
    status_summary_text,
    support_reply,
    welcome_message,
)
from casino_bot.telegram_bot.user_ops import (
    ensure_telegram_user,
    get_user_by_telegram_id,
    resolve_balance_reply,
)


def test_settings_allow_empty_telegram_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Hermetic defaults: developer shell / project .env may set TELEGRAM_* while tests run from repo root.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_ENABLED", raising=False)
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


def test_status_summary_text_shape() -> None:
    ok = status_summary_text(database_ready=True)
    assert "Liveness: ok" in ok
    assert "Database readiness: ok" in ok
    bad = status_summary_text(database_ready=False)
    assert "unavailable" in bad


def test_database_ready_for_status_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import casino_bot.telegram_bot.handlers as h

    monkeypatch.setattr(h, "check_database_ready", lambda: None)
    monkeypatch.setattr(h.settings, "ENVIRONMENT", "development", raising=False)
    monkeypatch.setattr(h.settings, "DRILL_FORCE_DB_NOT_READY", False, raising=False)
    assert database_ready_for_status() is True


def test_database_ready_for_status_drill(monkeypatch: pytest.MonkeyPatch) -> None:
    import casino_bot.telegram_bot.handlers as h

    monkeypatch.setattr(h.settings, "ENVIRONMENT", "development", raising=False)
    monkeypatch.setattr(h.settings, "DRILL_FORCE_DB_NOT_READY", True, raising=False)
    assert database_ready_for_status() is False


def test_database_ready_for_status_db_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import casino_bot.telegram_bot.handlers as h

    def boom() -> None:
        raise RuntimeError("simulated db failure")

    monkeypatch.setattr(h, "check_database_ready", boom)
    monkeypatch.setattr(h.settings, "ENVIRONMENT", "development", raising=False)
    monkeypatch.setattr(h.settings, "DRILL_FORCE_DB_NOT_READY", False, raising=False)
    assert database_ready_for_status() is False


def test_database_ready_drill_ignored_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import casino_bot.telegram_bot.handlers as h

    called: list[int] = []

    def mark() -> None:
        called.append(1)

    monkeypatch.setattr(h, "check_database_ready", mark)
    monkeypatch.setattr(h.settings, "ENVIRONMENT", "production", raising=False)
    monkeypatch.setattr(h.settings, "DRILL_FORCE_DB_NOT_READY", True, raising=False)
    assert database_ready_for_status() is True
    assert called == [1]


def test_profile_message_shape() -> None:
    text = profile_message(
        internal_user_id=7,
        telegram_user_id=99,
        is_active=False,
        created_at_iso="2026-05-01T12:00:00+00:00",
    )
    assert "7" in text and "99" in text
    assert "inactive" in text
    assert "2026-05-01" in text


def test_admin_message_points_at_v1_admin() -> None:
    body = admin_message()
    assert "/api/v1/admin/" in body
    assert "POST /api/v1/admin/login" in body


def test_support_reply_empty_config() -> None:
    assert support_reply(support_text="", contact_url="") == GENERIC_SUPPORT_LINE


def test_support_reply_with_text_and_url() -> None:
    body = support_reply(
        support_text="Email us at support@example.com",
        contact_url="https://example.com/help",
    )
    assert "support@example.com" in body
    assert "https://example.com/help" in body


def test_help_message_lists_new_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    import casino_bot.settings as smod

    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip"])
    monkeypatch.setattr(smod, "settings", cfg)
    body = help_message()
    for cmd in (
        "/flip",
        "/games",
        "/rounds",
        "/status",
        "/profile",
        "/admin",
        "/support",
    ):
        assert cmd in body
    assert "/wheel" not in body


def test_help_message_includes_wheel_when_bonus_wheel_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import casino_bot.settings as smod

    cfg = Settings(_env_file=None, GAMES_ENABLED=["coin_flip", "bonus_wheel"])
    monkeypatch.setattr(smod, "settings", cfg)
    body = help_message()
    assert "/wheel" in body


def test_settings_telegram_support_text_unescape() -> None:
    cfg = Settings(_env_file=None, TELEGRAM_SUPPORT_TEXT=r"Hello\nWorld")
    assert cfg.TELEGRAM_SUPPORT_TEXT == "Hello\nWorld"


def test_flip_reply_rejected_insufficient_balance() -> None:
    from casino_bot.telegram_bot.handlers import (
        _FlipSnapshot,
        _flip_reply_from_snapshot,
    )

    snap = _FlipSnapshot(
        game_id="coin_flip",
        status="rejected",
        details={
            "rejection_reason": "Operation would result in negative balance",
        },
        balance_line="Token balance: 0",
        user_id=1,
        bet_amount=10,
        idempotent_replay=False,
    )
    body = _flip_reply_from_snapshot(snap)
    assert "Not enough tokens" in body


def test_flip_reply_win_lose_committed() -> None:
    from casino_bot.telegram_bot.handlers import (
        _FlipSnapshot,
        _flip_reply_from_snapshot,
    )

    win = _FlipSnapshot(
        game_id="coin_flip",
        status="committed",
        details={"outcome": "win"},
        balance_line="Token balance: 11",
        user_id=1,
        bet_amount=10,
        idempotent_replay=False,
    )
    assert "Result: Win" in _flip_reply_from_snapshot(win)
    lose = _FlipSnapshot(
        game_id="coin_flip",
        status="committed",
        details={"outcome": "lose"},
        balance_line="Token balance: 9",
        user_id=1,
        bet_amount=10,
        idempotent_replay=False,
    )
    assert "Result: Lose" in _flip_reply_from_snapshot(lose)


def test_wheel_reply_bust_committed() -> None:
    from casino_bot.telegram_bot.handlers import (
        _FlipSnapshot,
        _flip_reply_from_snapshot,
    )

    snap = _FlipSnapshot(
        game_id="bonus_wheel",
        status="committed",
        details={"outcome": "bust", "payout_delta_units": -10_000},
        balance_line="Token balance: 40",
        user_id=1,
        bet_amount=10,
        idempotent_replay=False,
    )
    body = _flip_reply_from_snapshot(snap)
    assert "Bonus wheel" in body
    assert "Bust" in body
    assert "-10" in body
