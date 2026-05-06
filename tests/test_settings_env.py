"""Settings loading from environment (.env / process env) edge cases."""

from __future__ import annotations

import pytest

from casino_bot.settings import DEV_DATABASE_URL, DEV_USER_API_INTERNAL_TOKEN, Settings


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


def test_invalid_json_cors_origins_is_clear_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "http://localhost:3000")
    from pydantic_settings.sources import SettingsError

    with pytest.raises(SettingsError):
        Settings(_env_file=None)


def test_production_rejects_default_user_api_internal_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db"
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("JWT_SIGNING_KEY", "y" * 32)
    monkeypatch.setenv("REFRESH_TOKEN_PEPPER", "z" * 32)
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://admin.example.com"]')
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com")
    monkeypatch.setenv("BILLING_ALLOWED_RETURN_HOSTS", "admin.example.com")
    monkeypatch.setenv("USER_API_INTERNAL_TOKEN", DEV_USER_API_INTERNAL_TOKEN)
    with pytest.raises(ValueError, match="USER_API_INTERNAL_TOKEN"):
        Settings(_env_file=None)


def test_production_rejects_localhost_in_allowed_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db"
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("JWT_SIGNING_KEY", "y" * 32)
    monkeypatch.setenv("REFRESH_TOKEN_PEPPER", "z" * 32)
    monkeypatch.setenv("USER_API_INTERNAL_TOKEN", "prod-token-" + "a" * 24)
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://admin.example.com"]')
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com,localhost")
    with pytest.raises(ValueError, match="ALLOWED_HOSTS"):
        Settings(_env_file=None)


def test_billing_allowed_return_hosts_rejects_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BILLING_ALLOWED_RETURN_HOSTS", "*.example.com")
    with pytest.raises(ValueError, match="BILLING_ALLOWED_RETURN_HOSTS"):
        Settings(_env_file=None)


def test_return_url_allowlist_does_not_allow_subdomain_bypass(monkeypatch):
    from casino_bot.services.billing_service import _validate_return_url

    monkeypatch.setattr(
        "casino_bot.settings.settings",
        Settings(_env_file=None, BILLING_ALLOWED_RETURN_HOSTS=["admin.example.com"]),
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        _validate_return_url("https://evil.admin.example.com/return")


def test_github_actions_style_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mirror the production env gate used in CI."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db"
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "prod_secret_key_minimum_length_32__")
    monkeypatch.setenv("JWT_SIGNING_KEY", "prod_jwt_signing_key_minimum_len_32")
    monkeypatch.setenv("REFRESH_TOKEN_PEPPER", "prod_refresh_pepper_minimum_len_32")
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://admin.example.com"]')
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com")
    monkeypatch.setenv("BILLING_ALLOWED_RETURN_HOSTS", "admin.example.com")
    monkeypatch.setenv(
        "USER_API_INTERNAL_TOKEN", "prod_user_api_internal_token_min_len_32_____"
    )
    cfg = Settings(_env_file=None)
    assert cfg.DATABASE_URL != DEV_DATABASE_URL
    assert cfg.ALLOWED_HOSTS == ["api.example.com"]


def test_production_rejects_drill_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db"
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("JWT_SIGNING_KEY", "y" * 32)
    monkeypatch.setenv("REFRESH_TOKEN_PEPPER", "z" * 32)
    monkeypatch.setenv("USER_API_INTERNAL_TOKEN", "prod-token-" + "a" * 24)
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", '["https://admin.example.com"]')
    monkeypatch.setenv("ALLOWED_HOSTS", "api.example.com")
    monkeypatch.setenv("BILLING_ALLOWED_RETURN_HOSTS", "admin.example.com")
    monkeypatch.setenv("DRILL_FORCE_500_ON_PATH", "/health")
    with pytest.raises(ValueError, match="DRILL_FORCE_500_ON_PATH"):
        Settings(_env_file=None)
