from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from casino_bot.admin.models import AdminSession, AdminUser
from casino_bot.core.database import get_db
from casino_bot.core.security import TOKEN_TYPE_ACCESS, create_access_token, utcnow
from casino_bot.main import app
from casino_bot.settings import Settings, settings


def _stub_hash(password: str) -> str:
    return f"stub${password}"


def _stub_verify(password: str, password_hash: str) -> bool:
    return password_hash == _stub_hash(password)


@pytest.fixture
def security_client(sqlite_session, monkeypatch):
    monkeypatch.setattr("casino_bot.core.security.verify_password", _stub_verify)
    monkeypatch.setattr("casino_bot.core.security.hash_password", _stub_hash)
    monkeypatch.setattr("casino_bot.admin.login_service.verify_password", _stub_verify)
    monkeypatch.setattr(
        "casino_bot.admin.security_service.verify_password", _stub_verify
    )

    sqlite_session.add(
        AdminUser(
            email="admin@test.com",
            password_hash=_stub_hash("secretpass12"),
            role="admin",
            is_active=True,
        )
    )
    sqlite_session.add(
        AdminUser(
            email="super@test.com",
            password_hash=_stub_hash("superpass12"),
            role="superadmin",
            is_active=True,
        )
    )
    sqlite_session.commit()

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, sqlite_session
    app.dependency_overrides.clear()


def _login(
    client: TestClient, username: str = "admin@test.com", password: str = "secretpass12"
) -> dict:
    response = client.post(
        "/api/v1/admin/login", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body and "refresh_token" in body
    return body


def test_refresh_rotation_and_reuse_blocked(security_client):
    client, _ = security_client
    login = _login(client)
    first_refresh = login["refresh_token"]

    refreshed = client.post(
        "/api/v1/admin/refresh", json={"refresh_token": first_refresh}
    )
    assert refreshed.status_code == 200
    second_refresh = refreshed.json()["refresh_token"]
    assert second_refresh != first_refresh

    reused = client.post("/api/v1/admin/refresh", json={"refresh_token": first_refresh})
    assert reused.status_code == 401


def test_logout_and_logout_all_revoke_sessions(security_client):
    client, db = security_client
    login = _login(client)
    refresh = login["refresh_token"]

    logout = client.post("/api/v1/admin/logout", json={"refresh_token": refresh})
    assert logout.status_code == 200

    blocked = client.post("/api/v1/admin/refresh", json={"refresh_token": refresh})
    assert blocked.status_code == 401

    first = _login(client)
    second = _login(client)
    access = second["access_token"]
    out = client.post(
        "/api/v1/admin/logout-all",
        json={},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert out.status_code == 200
    assert out.json()["revoked_sessions"] >= 2

    active = db.query(AdminSession).filter(AdminSession.revoked_at.is_(None)).all()
    assert active == []

    stale = client.post(
        "/api/v1/admin/refresh", json={"refresh_token": first["refresh_token"]}
    )
    assert stale.status_code == 401


def test_refresh_wrong_token_type_rejected(security_client):
    client, _ = security_client
    login = _login(client)
    wrong = client.post(
        "/api/v1/admin/refresh", json={"refresh_token": login["access_token"]}
    )
    assert wrong.status_code == 401


def test_expired_refresh_token_rejected(security_client):
    client, db = security_client
    login = _login(client)
    payload = jwt.get_unverified_claims(login["refresh_token"])
    sid = payload["sid"]
    row = db.query(AdminSession).filter_by(id=sid).first()
    assert row is not None
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    res = client.post(
        "/api/v1/admin/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert res.status_code == 401


def test_bruteforce_lockout(security_client):
    client, _ = security_client
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        bad = client.post(
            "/api/v1/admin/login",
            data={"username": "admin@test.com", "password": "wrong"},
        )
        assert bad.status_code == 401

    locked = client.post(
        "/api/v1/admin/login",
        data={"username": "admin@test.com", "password": "secretpass12"},
    )
    assert locked.status_code == 429


def test_access_claims_include_type_and_jti():
    token, jti, _ = create_access_token("admin@test.com", "admin")
    payload = jwt.get_unverified_claims(token)
    assert payload["type"] == TOKEN_TYPE_ACCESS
    assert payload["jti"] == jti
    assert payload["sub"] == "admin@test.com"


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValueError):
        Settings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+psycopg://casino:secret@localhost:5432/casino_db",
            SECRET_KEY="x" * 32,
            JWT_SIGNING_KEY="y" * 32,
            REFRESH_TOKEN_PEPPER="z" * 32,
            CORS_ALLOW_ORIGINS=["*"],
            ALLOWED_HOSTS=["api.example.com"],
        )


def test_login_rate_limit_exceeded(security_client, monkeypatch):
    client, _ = security_client
    monkeypatch.setattr(settings, "LOGIN_RATE_LIMIT_PER_MINUTE", 2)
    client.post(
        "/api/v1/admin/login", data={"username": "x@test.com", "password": "bad"}
    )
    client.post(
        "/api/v1/admin/login", data={"username": "x@test.com", "password": "bad"}
    )
    third = client.post(
        "/api/v1/admin/login", data={"username": "x@test.com", "password": "bad"}
    )
    assert third.status_code == 429
    assert "Rate limit exceeded" in third.text
