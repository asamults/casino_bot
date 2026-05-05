from __future__ import annotations

from fastapi.testclient import TestClient

from casino_bot.admin.models import AdminUser
from casino_bot.core.database import get_db
from casino_bot.db.models import BillingWebhookEvent, Subscription, User
from casino_bot.main import app


def _stub_hash(password: str) -> str:
    return f"stub${password}"


def _stub_verify(password: str, password_hash: str) -> bool:
    return password_hash == _stub_hash(password)


def _admin_token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/admin/login",
        data={"username": "super@test.com", "password": "superpass12"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_billing_metrics_aggregation(sqlite_session, monkeypatch):
    monkeypatch.setattr("casino_bot.core.security.verify_password", _stub_verify)
    monkeypatch.setattr(
        "casino_bot.admin.security_service.verify_password", _stub_verify
    )
    sqlite_session.add(
        AdminUser(
            email="super@test.com",
            password_hash=_stub_hash("superpass12"),
            role="superadmin",
            is_active=True,
        )
    )
    sqlite_session.add(User(id=1, is_active=True))
    sqlite_session.add(User(id=2, is_active=True))
    sqlite_session.add(User(id=3, is_active=True))
    sqlite_session.add(
        Subscription(
            user_id=1,
            provider="stripe",
            status="active",
            plan_code="pro_monthly",
            entitlement_active=True,
        )
    )
    sqlite_session.add(
        Subscription(
            user_id=2,
            provider="stripe",
            status="trialing",
            plan_code="pro_monthly",
            entitlement_active=True,
        )
    )
    sqlite_session.add(
        Subscription(
            user_id=3,
            provider="stripe",
            status="canceled",
            plan_code="pro_monthly",
            entitlement_active=False,
        )
    )
    sqlite_session.add(
        BillingWebhookEvent(
            provider="stripe",
            external_event_id="evt_fail",
            event_type="x",
            status="failed",
        )
    )
    sqlite_session.commit()

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        token = _admin_token(client)
        res = client.get(
            "/api/v1/admin/billing/metrics",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["active_subscriptions"] == 2
        assert body["trialing_count"] == 1
        assert body["canceled_subscriptions"] == 1
        assert body["webhook_failed_count"] >= 1
    app.dependency_overrides.clear()
