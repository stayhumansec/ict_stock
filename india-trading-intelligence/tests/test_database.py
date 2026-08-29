from datetime import datetime, timedelta, timezone

import pytest

from backend.database import db
from backend.database.models import NotificationRecord, SignalRecord

KOLKATA = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def conn():
    connection = db.connect(":memory:")
    yield connection
    connection.close()


def make_signal(**overrides):
    defaults = dict(
        id=None,
        instrument="NIFTY",
        mode="SMC",
        direction="BULLISH",
        state="DEVELOPING",
        created_index=10,
        created_at=datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA),
        updated_at=datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA),
        entry=None,
        stop_loss=None,
        targets_json="[]",
        structure_event_ids_json="[0]",
        notes="",
    )
    defaults.update(overrides)
    return SignalRecord(**defaults)


def test_insert_and_get_signal(conn):
    signal_id = db.insert_signal(conn, make_signal())
    assert signal_id is not None

    fetched = db.get_signal(conn, signal_id)
    assert fetched is not None
    assert fetched.instrument == "NIFTY"
    assert fetched.state == "DEVELOPING"
    assert fetched.structure_event_ids_json == "[0]"


def test_get_missing_signal_returns_none(conn):
    assert db.get_signal(conn, 999) is None


def test_update_signal_state(conn):
    signal_id = db.insert_signal(conn, make_signal())
    new_time = datetime(2024, 1, 1, 9, 30, tzinfo=KOLKATA)
    db.update_signal_state(conn, signal_id, "CONFIRMED", new_time, structure_event_ids_json="[0, 5]")

    fetched = db.get_signal(conn, signal_id)
    assert fetched.state == "CONFIRMED"
    assert fetched.structure_event_ids_json == "[0, 5]"
    assert fetched.updated_at == new_time


def test_list_signals_filters_by_state(conn):
    db.insert_signal(conn, make_signal(state="DEVELOPING"))
    db.insert_signal(conn, make_signal(state="CONFIRMED"))
    db.insert_signal(conn, make_signal(state="INVALIDATED"))

    active = db.list_signals(conn, states=["DEVELOPING", "CONFIRMED"])
    assert len(active) == 2
    assert all(s.state in ("DEVELOPING", "CONFIRMED") for s in active)


def test_list_signals_no_filter_returns_all(conn):
    db.insert_signal(conn, make_signal())
    db.insert_signal(conn, make_signal())
    assert len(db.list_signals(conn)) == 2


def test_list_signals_ordered_by_updated_at_desc(conn):
    db.insert_signal(conn, make_signal(updated_at=datetime(2024, 1, 1, 9, 0, tzinfo=KOLKATA)))
    db.insert_signal(conn, make_signal(updated_at=datetime(2024, 1, 1, 10, 0, tzinfo=KOLKATA)))
    signals = db.list_signals(conn)
    assert signals[0].updated_at > signals[1].updated_at


def test_insert_and_list_notifications(conn):
    signal_id = db.insert_signal(conn, make_signal())
    record = NotificationRecord(
        id=None,
        signal_id=signal_id,
        channel="telegram",
        severity="SETUP",
        message="test alert",
        success=True,
        sent_at=datetime(2024, 1, 1, 9, 16, tzinfo=KOLKATA),
    )
    db.insert_notification(conn, record)

    all_notifs = db.list_notifications(conn)
    assert len(all_notifs) == 1
    assert all_notifs[0].message == "test alert"

    for_signal = db.list_notifications(conn, signal_id=signal_id)
    assert len(for_signal) == 1

    for_other_signal = db.list_notifications(conn, signal_id=9999)
    assert for_other_signal == []


def test_targets_and_event_ids_json_round_trip():
    assert db.targets_to_json([100.0, 200.0]) == "[100.0, 200.0]"
    assert db.event_ids_to_json([1, 2, 3]) == "[1, 2, 3]"
