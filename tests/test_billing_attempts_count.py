from __future__ import annotations

import pytest
from fastapi import HTTPException


def test_attempts_count_increments_once_on_processing_error(
    sqlite_session, monkeypatch
):
    from casino_bot.services import billing_service as bs

    class StubEvent:
        provider = "stripe"
        external_event_id = "evt_test_1"
        event_type = "customer.subscription.updated"
        status = "active"
        user_hint = None
        customer_id = None
        subscription_id = None
        plan_code = None
        current_period_end = None
        cancel_at_period_end = None
        raw = {}

    row = bs.BillingWebhookEvent(
        provider="stripe",
        external_event_id="evt_test_1",
        event_type="x",
        payload_hash="h",
        status="received",
        raw_payload={},
    )
    sqlite_session.add(row)
    sqlite_session.flush()

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(bs, "_resolve_user", boom)

    with pytest.raises(HTTPException):
        bs.safe_process_webhook(sqlite_session, event_row=row, event=StubEvent())

    assert row.attempts_count == 1
