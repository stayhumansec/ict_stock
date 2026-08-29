"""Persistence schema.

SQLite via the standard library (no ORM) - the project has stayed
dependency-light throughout, and this schema is simple enough not to
need one. See db.py for the actual table creation and repository
functions; this module only defines the record shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class SignalRecord:
    """Mirrors backend/signals/signal.py's Signal, but flattened for
    storage - structure_event_ids/targets are stored as JSON text."""

    id: Optional[int]
    instrument: str
    mode: str
    direction: str
    state: str
    created_index: int
    created_at: datetime
    updated_at: datetime
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    targets_json: str = "[]"
    structure_event_ids_json: str = "[]"
    notes: str = ""

    # Confluence summary (backend/signals/reasoning.py) - a transparent,
    # rule-based composite computed from real detected events, never a
    # probability. None until at least one CHoCH has confirmed.
    score: Optional[int] = None
    grade: Optional[str] = None
    data_quality: Optional[str] = None
    decision: Optional[str] = None
    reasoning_chain_json: str = "[]"
    core_signal_json: str = "[]"
    confirmations_json: str = "[]"
    conflicts_json: str = "[]"


@dataclass
class TradeRecord:
    """A manually-executed trade the trader logs against a signal.
    Nothing in this codebase writes to this table automatically - Release
    1 has no fill/execution feedback, so trades are only ever recorded
    when a human reports one happened."""

    id: Optional[int]
    signal_id: Optional[int]
    instrument: str
    direction: str
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    opened_at: datetime
    closed_at: Optional[datetime] = None
    pnl: Optional[float] = None
    notes: str = ""


@dataclass
class OrderRecord:
    """Shape only - Release 1 never writes to this table, since no order
    path exists. Present so a later release's execution layer has
    somewhere to log to without a schema migration."""

    id: Optional[int]
    trade_id: Optional[int]
    broker_order_id: str
    status: str
    raw_response_json: str = "{}"
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NotificationRecord:
    id: Optional[int]
    signal_id: Optional[int]
    channel: str
    severity: str
    message: str
    success: bool
    sent_at: datetime
    error: str = ""
