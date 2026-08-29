"""SQLite persistence layer: schema creation + repository functions.

No ORM - plain sqlite3 with parametrized queries. Datetimes are stored as
ISO8601 strings; JSON-shaped fields (targets, structure_event_ids) are
stored as JSON text since SQLite has no native array type.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import List, Optional

from .models import NotificationRecord, SignalRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instrument TEXT NOT NULL,
    mode TEXT NOT NULL,
    direction TEXT NOT NULL,
    state TEXT NOT NULL,
    created_index INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    entry REAL,
    stop_loss REAL,
    targets_json TEXT NOT NULL DEFAULT '[]',
    structure_event_ids_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER REFERENCES signals(id),
    instrument TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    quantity INTEGER NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    pnl REAL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER REFERENCES trades(id),
    broker_order_id TEXT NOT NULL,
    status TEXT NOT NULL,
    raw_response_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER REFERENCES signals(id),
    channel TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    success INTEGER NOT NULL,
    sent_at TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT ''
);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _row_to_signal(row: sqlite3.Row) -> SignalRecord:
    return SignalRecord(
        id=row["id"],
        instrument=row["instrument"],
        mode=row["mode"],
        direction=row["direction"],
        state=row["state"],
        created_index=row["created_index"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
        entry=row["entry"],
        stop_loss=row["stop_loss"],
        targets_json=row["targets_json"],
        structure_event_ids_json=row["structure_event_ids_json"],
        notes=row["notes"],
    )


def insert_signal(conn: sqlite3.Connection, record: SignalRecord) -> int:
    cur = conn.execute(
        """INSERT INTO signals
           (instrument, mode, direction, state, created_index, created_at, updated_at,
            entry, stop_loss, targets_json, structure_event_ids_json, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.instrument,
            record.mode,
            record.direction,
            record.state,
            record.created_index,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
            record.entry,
            record.stop_loss,
            record.targets_json,
            record.structure_event_ids_json,
            record.notes,
        ),
    )
    conn.commit()
    return cur.lastrowid


def update_signal_state(
    conn: sqlite3.Connection,
    signal_id: int,
    state: str,
    updated_at: datetime,
    structure_event_ids_json: Optional[str] = None,
) -> None:
    if structure_event_ids_json is not None:
        conn.execute(
            "UPDATE signals SET state = ?, updated_at = ?, structure_event_ids_json = ? WHERE id = ?",
            (state, updated_at.isoformat(), structure_event_ids_json, signal_id),
        )
    else:
        conn.execute(
            "UPDATE signals SET state = ?, updated_at = ? WHERE id = ?",
            (state, updated_at.isoformat(), signal_id),
        )
    conn.commit()


def get_signal(conn: sqlite3.Connection, signal_id: int) -> Optional[SignalRecord]:
    row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
    return _row_to_signal(row) if row else None


def list_signals(conn: sqlite3.Connection, states: Optional[List[str]] = None) -> List[SignalRecord]:
    if states:
        placeholders = ",".join("?" for _ in states)
        rows = conn.execute(
            f"SELECT * FROM signals WHERE state IN ({placeholders}) ORDER BY updated_at DESC", states
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM signals ORDER BY updated_at DESC").fetchall()
    return [_row_to_signal(r) for r in rows]


def insert_notification(conn: sqlite3.Connection, record: NotificationRecord) -> int:
    cur = conn.execute(
        """INSERT INTO notifications (signal_id, channel, severity, message, success, sent_at, error)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            record.signal_id,
            record.channel,
            record.severity,
            record.message,
            1 if record.success else 0,
            record.sent_at.isoformat(),
            record.error,
        ),
    )
    conn.commit()
    return cur.lastrowid


def list_notifications(conn: sqlite3.Connection, signal_id: Optional[int] = None) -> List[NotificationRecord]:
    if signal_id is not None:
        rows = conn.execute(
            "SELECT * FROM notifications WHERE signal_id = ? ORDER BY sent_at DESC", (signal_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM notifications ORDER BY sent_at DESC").fetchall()

    return [
        NotificationRecord(
            id=r["id"],
            signal_id=r["signal_id"],
            channel=r["channel"],
            severity=r["severity"],
            message=r["message"],
            success=bool(r["success"]),
            sent_at=datetime.fromisoformat(r["sent_at"]),
            error=r["error"],
        )
        for r in rows
    ]


def targets_to_json(targets: List[float]) -> str:
    return json.dumps(targets)


def event_ids_to_json(ids: List[int]) -> str:
    return json.dumps(ids)
