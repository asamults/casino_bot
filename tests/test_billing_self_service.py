from __future__ import annotations

from fastapi.testclient import TestClient

from casino_bot.core.database import get_db
from casino_bot.db.models import Subscription, User
from casino_bot.main import app
from casino_bot.settings import settings


def _headers(user_id: int = 1) -> dict[str, str]:
    return {
        "x-user-id": str(user_id),
        "x-internal-token": settings.USER_API_INTERNAL_TOKEN,
    }


def test_me_subscription_cancel_resume_and_portal(sqlite_session, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ALLOWED_RETURN_HOSTS", ["example.com"])
    sqlite_session.add(User(id=1, is_active=True, billing_customer_id="cus_123"))
    sqlite_session.add(
        Subscription(
            user_id=1,
            provider="stripe",
            provider_subscription_id="sub_123",
            status="active",
            plan_code="pro_monthly",
            entitlement_active=True,
        )
    )
    sqlite_session.commit()

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        me = client.get("/api/v1/billing/me/subscription", headers=_headers())
        assert me.status_code == 200
        assert me.json()["subscription"]["status"] == "active"

        cancel = client.post(
            "/api/v1/billing/me/subscription/cancel", headers=_headers()
        )
        assert cancel.status_code == 200
        assert cancel.json()["cancel_at_period_end"] is True

        resume = client.post(
            "/api/v1/billing/me/subscription/resume", headers=_headers()
        )
        assert resume.status_code == 200
        assert resume.json()["cancel_at_period_end"] is False

        portal = client.post(
            "/api/v1/billing/me/portal",
            json={"return_url": "https://example.com/account"},
            headers=_headers(),
        )
        assert portal.status_code == 200
        assert "portal_url" in portal.json()
    app.dependency_overrides.clear()


def test_self_service_requires_identity(sqlite_session):
    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        res = client.get("/api/v1/billing/me/subscription")
        assert res.status_code == 401
    app.dependency_overrides.clear()
