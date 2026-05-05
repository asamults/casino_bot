"""Settings loading from environment (.env / process env) edge cases."""

from __future__ import annotations

import pytest

from casino_bot.settings import DEV_DATABASE_URL, Settings


def test_list_str_fields_accept_json_or_csv_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com,localhost")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://admin.example.com"]')
    cfg = Settings(_env_file=None)
    assert cfg.ALLOWED_HOSTS == ["api.example.com", "localhost"]
    assert cfg.CORS_ALLOW_ORIGINS == ["https://admin.example.com"]


def test_list_str_fields_accept_json_array_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOWED_HOSTS", '["a.example.com", "b.example.com"]')
    cfg = Settings(_env_file=None)
    assert cfg.ALLOWED_HOSTS == ["a.example.com", "b.example.com"]


def test_malformed_json_list_still_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALLOWED_HOSTS", '["unclosed"')
    from pydantic_settings.sources import SettingsError

    with pytest.raises(SettingsError):
        Settings(_env_file=None)


def test_github_actions_style_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror security-gates.yml env for migration steps (alembic imports settings).

    Use 127.0.0.1 (not localhost) so DATABASE_URL is not the dev default literal while
    still matching GitHub Actions Postgres on the runner.
    """
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db"
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "prod_secret_key_minimum_length_32__")
    monkeypatch.setenv("JWT_SIGNING_KEY", "prod_jwt_signing_key_minimum_len_32")
    monkeypatch.setenv("REFRESH_TOKEN_PEPPER", "prod_refresh_pepper_minimum_len_32")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://admin.example.com"]')
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com,localhost")
    cfg = Settings(_env_file=None)
    assert cfg.DATABASE_URL != DEV_DATABASE_URL
    assert cfg.ALLOWED_HOSTS == ["api.example.com", "localhost"]
