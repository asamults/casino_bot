import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

import casino_bot.main as main_mod
from casino_bot.db import session as session_mod
from casino_bot.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert "X-Request-ID" in r.headers


def test_health_preserves_request_id(client):
    r = client.get("/health", headers={"X-Request-ID": "custom-req-id"})
    assert r.status_code == 200
    assert r.headers.get("X-Request-ID") == "custom-req-id"


def test_ready_ok(monkeypatch):
    eng = create_engine("sqlite+pysqlite:///:memory:", future=True)
    monkeypatch.setattr(session_mod, "readiness_engine", eng)
    with TestClient(app) as client:
        r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


def test_ready_503(monkeypatch):
    def fail():
        raise RuntimeError("simulated db failure")

    monkeypatch.setattr(main_mod, "check_database_ready", fail)
    with TestClient(app) as client:
        r = client.get("/ready")
    assert r.status_code == 503
