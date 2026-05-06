from __future__ import annotations

import pytest

from casino_bot.admin.deps import superadmin_guard
from casino_bot.settings import Settings


def test_dev_allows_drill_superadmin_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "casino_bot.admin.deps.settings",
        Settings(_env_file=None, DRILL_SUPERADMIN_TOKEN="drill-token"),
    )
    dep = superadmin_guard()
    payload = dep(token="drill-token")
    assert payload["role"] == "superadmin"


def test_production_rejects_drill_superadmin_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "casino_bot.admin.deps.settings",
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+psycopg://casino:secret@127.0.0.1:5432/casino_db",
            SECRET_KEY="x" * 32,
            JWT_SIGNING_KEY="y" * 32,
            REFRESH_TOKEN_PEPPER="z" * 32,
            USER_API_INTERNAL_TOKEN="prod-user-api-token-" + "a" * 32,
            CORS_ALLOW_ORIGINS=["https://admin.example.com"],
            ALLOWED_HOSTS=["api.example.com"],
            BILLING_ALLOWED_RETURN_HOSTS=["admin.example.com"],
        ),
    )
    dep = superadmin_guard()
    with pytest.raises(Exception):
        dep(token="anything-not-jwt")
