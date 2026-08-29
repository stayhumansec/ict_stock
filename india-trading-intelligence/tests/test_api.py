from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.database import db as database
from backend.database.models import SignalRecord

KOLKATA = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(server, "DB_PATH", db_path)
    return TestClient(server.app)


def make_signal(**overrides):
    defaults = dict(
        id=None,
        instrument="NIFTY",
        mode="SMC",
        direction="BEARISH",
        state="DEVELOPING",
        created_index=10,
        created_at=datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA),
        updated_at=datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA),
        reasoning_chain_json='["Bearish CHoCH confirmed at 100.00"]',
        core_signal_json='[{"kind": "CHOCH", "price": 100.0, "note": ""}]',
    )
    defaults.update(overrides)
    return SignalRecord(**defaults)


def _seed(db_path, records):
    conn = database.connect(db_path)
    ids = [database.insert_signal(conn, r) for r in records]
    conn.close()
    return ids


def test_list_all_signals_empty(client):
    resp = client.get("/api/signals")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_all_signals_returns_seeded_data(client):
    _seed(server.DB_PATH, [make_signal()])
    resp = client.get("/api/signals")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["instrument"] == "NIFTY"
    assert body[0]["direction"] == "BEARISH"
    assert body[0]["reasoningChain"] == ["Bearish CHoCH confirmed at 100.00"]
    assert body[0]["coreSignal"][0]["kind"] == "CHOCH"
    assert body[0]["riskReward"] is None


def test_active_endpoint_filters_by_state(client):
    _seed(
        server.DB_PATH,
        [
            make_signal(state="DEVELOPING"),
            make_signal(state="CONFIRMED"),
            make_signal(state="INVALIDATED"),
        ],
    )
    resp = client.get("/api/signals/active")
    body = resp.json()
    assert len(body) == 2
    assert all(s["state"] in ("DEVELOPING", "CONFIRMED") for s in body)


def test_resolved_endpoint_filters_by_state(client):
    _seed(
        server.DB_PATH,
        [
            make_signal(state="DEVELOPING"),
            make_signal(state="INVALIDATED"),
            make_signal(state="EXPIRED"),
        ],
    )
    resp = client.get("/api/signals/resolved")
    body = resp.json()
    assert len(body) == 2
    assert all(s["state"] in ("INVALIDATED", "EXPIRED") for s in body)


def test_get_single_signal(client):
    ids = _seed(server.DB_PATH, [make_signal()])
    resp = client.get(f"/api/signals/{ids[0]}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(ids[0])


def test_get_missing_signal_404s(client):
    resp = client.get("/api/signals/9999")
    assert resp.status_code == 404


def test_system_health_no_heartbeat_reports_disconnected(client):
    resp = client.get("/api/system-health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataFeedConnected"] is False
    assert body["lastTickAt"] is None
    assert body["automationEnabled"] is False


def test_system_health_fresh_heartbeat_reports_connected(client):
    conn = database.connect(server.DB_PATH)
    database.upsert_heartbeat(conn, "NIFTY", datetime.now(KOLKATA), 24000.0, "csv")
    conn.close()

    resp = client.get("/api/system-health")
    body = resp.json()
    assert body["dataFeedConnected"] is True
    assert body["lastTickAt"] is not None


def test_system_health_stale_heartbeat_reports_disconnected(client):
    conn = database.connect(server.DB_PATH)
    stale_time = datetime.now(KOLKATA) - timedelta(hours=2)
    database.upsert_heartbeat(conn, "NIFTY", stale_time, 24000.0, "csv")
    conn.close()

    resp = client.get("/api/system-health")
    body = resp.json()
    assert body["dataFeedConnected"] is False
