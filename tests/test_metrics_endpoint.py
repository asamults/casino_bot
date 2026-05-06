from __future__ import annotations

from fastapi.testclient import TestClient

from casino_bot.main import app


def test_metrics_endpoint_exposes_prometheus_metrics():
    with TestClient(app) as client:
        r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in (r.headers.get("content-type") or "")
    body = r.text
    assert "casino_bot_http_requests_total" in body
    assert "casino_bot_http_request_duration_seconds" in body
    assert "casino_bot_webhook_processed_total" in body
    assert "casino_bot_db_ready_state" in body
