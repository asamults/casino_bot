from __future__ import annotations

from fastapi.testclient import TestClient

from casino_bot.core.database import get_db
from casino_bot.db.models import User
from casino_bot.main import app
from casino_bot.settings import settings


def _headers(user_id: int = 1) -> dict[str, str]:
    return {
        "x-user-id": str(user_id),
        "x-internal-token": settings.USER_API_INTERNAL_TOKEN,
    }


def test_checkout_valid_and_invalid_inputs(sqlite_session, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ENABLE_CHECKOUT", True)
    monkeypatch.setattr(settings, "BILLING_ALLOWED_PLANS", ["pro_monthly"])
    monkeypatch.setattr(settings, "BILLING_ALLOWED_RETURN_HOSTS", ["example.com"])
    sqlite_session.add(User(id=1, is_active=True))
    sqlite_session.commit()

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        ok = client.post(
            "/api/v1/billing/checkout/session",
            json={
                "plan_code": "pro_monthly",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
            headers=_headers(),
        )
        assert ok.status_code == 200
        assert "checkout_url" in ok.json()

        bad_plan = client.post(
            "/api/v1/billing/checkout/session",
            json={
                "plan_code": "evil_plan",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
            headers=_headers(),
        )
        assert bad_plan.status_code == 400
        assert bad_plan.json()["detail"]["code"] == "INVALID_PLAN_CODE"

        bad_url = client.post(
            "/api/v1/billing/checkout/session",
            json={
                "plan_code": "pro_monthly",
                "success_url": "https://attacker.com/success",
                "cancel_url": "https://example.com/cancel",
            },
            headers=_headers(),
        )
        assert bad_url.status_code == 400
        assert bad_url.json()["detail"]["code"] == "INVALID_RETURN_URL"
    app.dependency_overrides.clear()


def test_checkout_rate_limit_headers_present(sqlite_session, monkeypatch):
    monkeypatch.setattr(settings, "BILLING_ENABLE_CHECKOUT", True)
    monkeypatch.setattr(settings, "BILLING_ALLOWED_PLANS", ["pro_monthly"])
    monkeypatch.setattr(settings, "BILLING_ALLOWED_RETURN_HOSTS", ["example.com"])
    sqlite_session.add(User(id=1, is_active=True))
    sqlite_session.commit()

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        res = client.post(
            "/api/v1/billing/checkout/session",
            json={
                "plan_code": "pro_monthly",
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
            headers=_headers(),
        )
        assert res.status_code == 200
        assert "X-RateLimit-Limit" in res.headers
    app.dependency_overrides.clear()
