"""Admin API v1 — auth, RBAC, compliance error shape (SQLite + dependency overrides)."""

import pytest
from fastapi.testclient import TestClient

from casino_bot.admin.models import AdminUser
from casino_bot.core.database import get_db
from casino_bot.main import app


def _stub_hash(password: str) -> str:
    return f"stub${password}"


def _stub_verify(password: str, password_hash: str) -> bool:
    return password_hash == _stub_hash(password)


@pytest.fixture
def admin_api_client(sqlite_session, monkeypatch):
    # Patch modules that bind ``verify_password`` / ``hash_password`` at import time.
    monkeypatch.setattr("casino_bot.core.security.verify_password", _stub_verify)
    monkeypatch.setattr("casino_bot.core.security.hash_password", _stub_hash)
    monkeypatch.setattr("casino_bot.admin.login_service.verify_password", _stub_verify)
    monkeypatch.setattr(
        "casino_bot.admin.security_service.verify_password", _stub_verify
    )
    monkeypatch.setattr(
        "casino_bot.services.admin_accounts_service.verify_password", _stub_verify
    )
    monkeypatch.setattr(
        "casino_bot.services.admin_accounts_service.hash_password", _stub_hash
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
        yield client
    app.dependency_overrides.clear()


def _token(client: TestClient, username: str, password: str) -> str:
    r = client.post(
        "/api/v1/admin/login",
        data={"username": username, "password": password},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_login_v1_and_legacy_login(admin_api_client: TestClient):
    t = _token(admin_api_client, "admin@test.com", "secretpass12")
    assert len(t) > 10
    r2 = admin_api_client.post(
        "/admin/login",
        data={"username": "admin@test.com", "password": "secretpass12"},
    )
    assert r2.status_code == 200


def test_list_users_empty(admin_api_client: TestClient):
    tok = _token(admin_api_client, "admin@test.com", "secretpass12")
    r = admin_api_client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0


def test_create_user_and_adjust_compliance_error(admin_api_client: TestClient):
    tok = _token(admin_api_client, "super@test.com", "superpass12")
    r = admin_api_client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"internal_note": "t"},
    )
    assert r.status_code == 201
    uid = r.json()["id"]
    activate = admin_api_client.post(
        f"/api/v1/admin/users/{uid}/subscription/activate-test",
        headers={"Authorization": f"Bearer {tok}"},
        json={"plan_code": "test_plan", "period_days": 30},
    )
    assert activate.status_code == 200

    r2 = admin_api_client.post(
        f"/api/v1/admin/users/{uid}/tokens/adjust",
        headers={"Authorization": f"Bearer {tok}"},
        json={"delta": -1.0, "reason": "test"},
    )
    assert r2.status_code == 409
    err = r2.json()
    assert err.get("code") == "COMPLIANCE_VIOLATION"
    assert "negative" in err.get("detail", "").lower()


def test_superadmin_create_admin(admin_api_client: TestClient):
    tok = _token(admin_api_client, "super@test.com", "superpass12")
    r = admin_api_client.post(
        "/api/v1/admin/admins",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "email": "new@test.com",
            "password": "longpass12",
            "role": "admin",
        },
    )
    assert r.status_code == 201
    assert r.json()["email"] == "new@test.com"


def test_admin_cannot_create_admin(admin_api_client: TestClient):
    tok = _token(admin_api_client, "admin@test.com", "secretpass12")
    r = admin_api_client.post(
        "/api/v1/admin/admins",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "email": "x@test.com",
            "password": "longpass12",
            "role": "admin",
        },
    )
    assert r.status_code == 403
