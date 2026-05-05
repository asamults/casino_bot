from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from casino_bot.admin.models import AdminUser
from casino_bot.core.database import get_db
from casino_bot.db.models import BillingWebhookEvent, Subscription, User
from casino_bot.main import app
from casino_bot.settings import settings


def _stub_hash(password: str) -> str:
    return f"stub${password}"


def _stub_verify(password: str, password_hash: str) -> bool:
    return password_hash == _stub_hash(password)


@pytest.fixture
def billing_client(sqlite_session, monkeypatch):
    monkeypatch.setattr("casino_bot.core.security.verify_password", _stub_verify)
    monkeypatch.setattr(
        "casino_bot.admin.security_service.verify_password", _stub_verify
    )
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_secret")

    admin = AdminUser(
        email="super@test.com",
        password_hash=_stub_hash("superpass12"),
        role="superadmin",
        is_active=True,
    )
    user = User(id=101, is_active=True, billing_customer_id="cus_123")
    sqlite_session.add(admin)
    sqlite_session.add(user)
    sqlite_session.commit()

    def override_get_db():
        yield sqlite_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, sqlite_session
    app.dependency_overrides.clear()


def _stripe_payload(
    event_id: str, *, customer="cus_123", sub_id="sub_001", status="active", user_id=101
):
    return {
        "id": event_id,
        "type": "customer.subscription.updated",
        "created": int(datetime.now(tz=UTC).timestamp()),
        "data": {
            "object": {
                "id": sub_id,
                "customer": customer,
                "status": status,
                "cancel_at_period_end": False,
                "current_period_end": int(
                    (datetime.now(tz=UTC) + timedelta(days=30)).timestamp()
                ),
                "items": {"data": [{"price": {"lookup_key": "pro_monthly"}}]},
                "metadata": {"user_id": str(user_id)},
            }
        },
    }


def _stripe_sig(secret: str, body: bytes, ts: str = "1700000000") -> str:
    if ts == "1700000000":
        ts = str(int(datetime.now(tz=UTC).timestamp()))
    signed = f"{ts}.{body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={digest}"


def _admin_token(client: TestClient) -> str:
    r = client.post(
        "/api/v1/admin/login",
        data={"username": "super@test.com", "password": "superpass12"},
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def test_valid_signature_and_idempotency(billing_client):
    client, db = billing_client
    payload = _stripe_payload("evt_1")
    raw = json.dumps(payload).encode("utf-8")
    headers = {"stripe-signature": _stripe_sig(settings.STRIPE_WEBHOOK_SECRET, raw)}

    first = client.post("/api/v1/billing/webhooks/stripe", data=raw, headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "processed"

    second = client.post("/api/v1/billing/webhooks/stripe", data=raw, headers=headers)
    assert second.status_code == 200
    assert second.json()["status"] == "idempotent"

    events = (
        db.query(BillingWebhookEvent)
        .filter_by(provider="stripe", external_event_id="evt_1")
        .all()
    )
    assert len(events) == 1


def test_invalid_signature_rejected(billing_client):
    client, _ = billing_client
    payload = _stripe_payload("evt_bad")
    raw = json.dumps(payload).encode("utf-8")
    bad = client.post(
        "/api/v1/billing/webhooks/stripe",
        data=raw,
        headers={"stripe-signature": "t=1,v1=deadbeef"},
    )
    assert bad.status_code == 401
    assert "secret" not in bad.text.lower()


def test_subscription_sync_and_entitlement_update(billing_client):
    client, db = billing_client
    created = _stripe_payload("evt_create", status="active")
    raw_create = json.dumps(created).encode("utf-8")
    headers_create = {
        "stripe-signature": _stripe_sig(settings.STRIPE_WEBHOOK_SECRET, raw_create)
    }
    r1 = client.post(
        "/api/v1/billing/webhooks/stripe", data=raw_create, headers=headers_create
    )
    assert r1.status_code == 200

    sub = db.query(Subscription).filter_by(provider_subscription_id="sub_001").first()
    assert sub is not None
    assert sub.status == "active"
    assert sub.entitlement_active is True

    canceled = _stripe_payload("evt_cancel", sub_id="sub_001", status="canceled")
    raw_cancel = json.dumps(canceled).encode("utf-8")
    headers_cancel = {
        "stripe-signature": _stripe_sig(settings.STRIPE_WEBHOOK_SECRET, raw_cancel)
    }
    r2 = client.post(
        "/api/v1/billing/webhooks/stripe", data=raw_cancel, headers=headers_cancel
    )
    assert r2.status_code == 200
    db.refresh(sub)
    assert sub.status == "canceled"
    assert sub.entitlement_active is False


def test_linking_fallback_customer_id_path(billing_client):
    client, db = billing_client
    payload = _stripe_payload("evt_customer_link", user_id=99999)
    raw = json.dumps(payload).encode("utf-8")
    headers = {"stripe-signature": _stripe_sig(settings.STRIPE_WEBHOOK_SECRET, raw)}
    res = client.post("/api/v1/billing/webhooks/stripe", data=raw, headers=headers)
    assert res.status_code == 200
    sub = db.query(Subscription).filter_by(provider_subscription_id="sub_001").first()
    assert sub is not None
    assert sub.user_id == 101


def test_unresolved_mapping_failed_status(billing_client):
    client, db = billing_client
    payload = _stripe_payload("evt_unresolved", customer="cus_not_found", user_id=99999)
    raw = json.dumps(payload).encode("utf-8")
    headers = {"stripe-signature": _stripe_sig(settings.STRIPE_WEBHOOK_SECRET, raw)}
    res = client.post("/api/v1/billing/webhooks/stripe", data=raw, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "failed"
    event = (
        db.query(BillingWebhookEvent)
        .filter_by(external_event_id="evt_unresolved")
        .first()
    )
    assert event is not None
    assert event.status == "failed"


def test_entitlement_enforcement_on_business_operation(billing_client):
    client, db = billing_client
    db.add(
        AdminUser(
            email="admin@test.com",
            password_hash=_stub_hash("adminpass12"),
            role="admin",
            is_active=True,
        )
    )
    db.commit()
    login = client.post(
        "/api/v1/admin/login",
        data={"username": "admin@test.com", "password": "adminpass12"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    create_user = client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"internal_note": "u"},
    )
    assert create_user.status_code == 201
    user_id = create_user.json()["id"]

    blocked = client.post(
        f"/api/v1/admin/users/{user_id}/tokens/adjust",
        headers={"Authorization": f"Bearer {token}"},
        json={"delta": 1.0, "reason": "test"},
    )
    assert blocked.status_code == 402

    db.add(
        Subscription(
            user_id=user_id,
            provider="internal",
            status="active",
            plan_code="test",
            entitlement_active=True,
        )
    )
    db.commit()

    allowed = client.post(
        f"/api/v1/admin/users/{user_id}/tokens/adjust",
        headers={"Authorization": f"Bearer {token}"},
        json={"delta": 1.0, "reason": "test"},
    )
    assert allowed.status_code == 200
