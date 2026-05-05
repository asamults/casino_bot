from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from casino_bot.admin.models import AdminUser
from casino_bot.core.database import get_db
from casino_bot.db.models import BillingWebhookEvent, User
from casino_bot.main import app


def _admin_token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/admin/login",
        data={"username": "super@test.com", "password": "superpass12"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _stub_hash(password: str) -> str:
    return f"stub${password}"


def _stub_verify(password: str, password_hash: str) -> bool:
    return password_hash == _stub_hash(password)


def test_replay_failed_and_processed(sqlite_session, monkeypatch):
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
    sqlite_session.add(User(id=101, is_active=True, billing_customer_id="cus_123"))
    sqlite_session.add(
        BillingWebhookEvent(
            provider="stripe",
            external_event_id="evt_replay",
            event_type="customer.subscription.updated",
            status="failed",
            raw_payload={
                "id": "evt_replay",
                "type": "customer.subscription.updated",
                "created": int(datetime.now(tz=UTC).timestamp()),
                "data": {
                    "object": {
                        "id": "sub_replay",
                        "customer": "cus_123",
                        "status": "active",
                        "cancel_at_period_end": False,
                        "items": {"data": [{"price": {"lookup_key": "pro_monthly"}}]},
                    }
                },
            },
        )
    )
    sqlite_session.commit()

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        token = _admin_token(client)
        replay = client.post(
            "/api/v1/admin/billing/events/1/replay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert replay.status_code == 200
        assert replay.json()["status"] in {"processed", "idempotent"}

        replay_again = client.post(
            "/api/v1/admin/billing/events/1/replay",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert replay_again.status_code == 200
    app.dependency_overrides.clear()
