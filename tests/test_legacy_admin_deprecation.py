from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from casino_bot.admin.models import AdminUser
from casino_bot.core.database import get_db
from casino_bot.main import app
from casino_bot.settings import settings


def _assert_legacy_headers(r):
    assert r.headers.get("Deprecation") == "true"
    assert "Sunset" in r.headers
    assert "Link" in r.headers


def _stub_hash(password: str) -> str:
    return f"stub${password}"


def _stub_verify(password: str, password_hash: str) -> bool:
    return password_hash == _stub_hash(password)


@pytest.fixture
def admin_api_client(sqlite_session, monkeypatch):
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
        yield client
    app.dependency_overrides.clear()


def test_legacy_login_has_deprecation_headers(admin_api_client: TestClient):
    r = admin_api_client.post(
        "/admin/login",
        data={"username": "admin@test.com", "password": "secretpass12"},
    )
    assert r.status_code == 200
    _assert_legacy_headers(r)


def test_legacy_admin_endpoint_has_deprecation_headers(admin_api_client: TestClient):
    r_login = admin_api_client.post(
        "/admin/login",
        data={"username": "admin@test.com", "password": "secretpass12"},
    )
    tok = r_login.json()["access_token"]
    r = admin_api_client.get(
        "/admin/ping",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    _assert_legacy_headers(r)


def test_v1_admin_endpoints_do_not_have_deprecation_headers(
    admin_api_client: TestClient,
):
    r_login = admin_api_client.post(
        "/api/v1/admin/login",
        data={"username": "admin@test.com", "password": "secretpass12"},
    )
    assert r_login.status_code == 200
    assert "Deprecation" not in r_login.headers
    assert "Sunset" not in r_login.headers

    tok = r_login.json()["access_token"]
    r = admin_api_client.get(
        "/api/v1/admin/ping",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    assert "Deprecation" not in r.headers
    assert "Sunset" not in r.headers


def test_legacy_disable_returns_410(
    admin_api_client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "LEGACY_ADMIN_DISABLE", True)
    r = admin_api_client.post(
        "/admin/login",
        data={"username": "admin@test.com", "password": "secretpass12"},
    )
    assert r.status_code == 410

    # v1 remains available
    r2 = admin_api_client.post(
        "/api/v1/admin/login",
        data={"username": "admin@test.com", "password": "secretpass12"},
    )
    assert r2.status_code == 200
