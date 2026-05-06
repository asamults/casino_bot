from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from casino_bot.admin.models import AdminUser
from casino_bot.core.database import get_db
from casino_bot.core.pii import mask_email, mask_token_like
from casino_bot.db.models import BillingWebhookEvent, User
from casino_bot.main import app
from casino_bot.settings import settings


def _stub_hash(password: str) -> str:
    return f"stub${password}"


def _stub_verify(password: str, password_hash: str) -> bool:
    return password_hash == _stub_hash(password)


@pytest.fixture
def admin_client(sqlite_session, monkeypatch):
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
    sqlite_session.commit()

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, sqlite_session
    app.dependency_overrides.clear()


def _admin_token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/admin/login",
        data={"username": "super@test.com", "password": "superpass12"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_masking_helpers():
    assert mask_token_like("cus_123456789") == "cus***789"
    assert mask_token_like("short") == "***"
    assert mask_email("user@example.com") in {"u***r@example.com", "u***@example.com"}


def test_dead_letter_threshold_on_replay(admin_client, monkeypatch):
    client, db = admin_client
    monkeypatch.setattr(settings, "BILLING_DEAD_LETTER_ATTEMPTS", 2)
    db.add(User(id=101, is_active=True, billing_customer_id="cus_exists"))
    db.add(
        BillingWebhookEvent(
            provider="stripe",
            external_event_id="evt_dl",
            event_type="customer.subscription.updated",
            status="failed",
            raw_payload={
                "id": "evt_dl",
                "type": "customer.subscription.updated",
                "created": int(datetime.now(tz=UTC).timestamp()),
                "data": {
                    "object": {
                        "id": "sub_x",
                        "customer": "cus_missing",
                        "status": "active",
                    }
                },
            },
        )
    )
    db.commit()

    token = _admin_token(client)
    r1 = client.post(
        "/api/v1/admin/billing/events/1/replay",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["dead_letter"] is False

    r2 = client.post(
        "/api/v1/admin/billing/events/1/replay",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    assert r2.json()["dead_letter"] is True


def test_retention_cleanup_service(admin_client, monkeypatch):
    _, db = admin_client
    monkeypatch.setattr(settings, "BILLING_WEBHOOK_RETENTION_DAYS", 1)
    old = datetime.now(tz=UTC) - timedelta(days=10)
    db.add(
        BillingWebhookEvent(
            provider="stripe",
            external_event_id="evt_old",
            event_type="x",
            status="processed",
            received_at=old,
        )
    )
    db.commit()
    from casino_bot.services.billing_service import cleanup_old_webhook_events

    out = cleanup_old_webhook_events(db, now=datetime.now(tz=UTC))
    assert out["deleted"] == 1
