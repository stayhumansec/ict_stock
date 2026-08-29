"""Read-only REST API over the SQLite database live/run_live_manual.py
writes to. Serves the frontend real signal/journal/system-health data.

Deliberately does NOT expose a market-overview endpoint: computing
market regime (trending/ranging/breakout/volatile) or session
(pre-open/morning/.../CAS) requires a classifier this project never
built - BUILD_SPEC.md scoped Release 1 to structure/liquidity detection,
not regime classification. The frontend keeps that screen mocked and
clearly labeled as such rather than this API fabricating it.

Run with: uvicorn backend.api.server:app --reload
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.database import db as database
from backend.database.models import SignalRecord
from backend.notifications.telegram import TelegramNotifier

DB_PATH = os.environ.get("SMC_DB_PATH", "smc.db")
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o]

# A heartbeat older than this is treated as "feed disconnected" rather
# than trusted as still live.
HEARTBEAT_STALE_SECONDS = 20 * 60

ACTIVE_STATES = ["DEVELOPING", "CONFIRMED", "ACTIVE"]
RESOLVED_STATES = ["TARGET_HIT", "STOP_HIT", "INVALIDATED", "EXPIRED"]

app = FastAPI(title="SMC Terminal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_conn():
    return database.connect(DB_PATH)


class StructureRefOut(BaseModel):
    kind: str
    price: float
    note: str = ""


class SignalOut(BaseModel):
    id: str
    instrument: str
    direction: str
    methodology: str
    state: str
    score: Optional[int]
    grade: Optional[str]
    createdAt: str
    updatedAt: str
    entry: Optional[float]
    stopLoss: Optional[float]
    targets: List[float]
    riskReward: Optional[float]
    coreSignal: List[StructureRefOut]
    confirmations: List[StructureRefOut]
    conflicts: List[StructureRefOut]
    reasoningChain: List[str]
    dataQuality: Optional[str]
    decision: Optional[str]


class SystemHealthOut(BaseModel):
    dataFeedConnected: bool
    lastTickAt: Optional[str]
    telegramConfigured: bool
    automationEnabled: bool


def _record_to_out(record: SignalRecord) -> SignalOut:
    return SignalOut(
        id=str(record.id),
        instrument=record.instrument,
        direction=record.direction,
        methodology=record.mode,
        state=record.state,
        score=record.score,
        grade=record.grade,
        createdAt=record.created_at.isoformat(),
        updatedAt=record.updated_at.isoformat(),
        entry=record.entry,
        stopLoss=record.stop_loss,
        targets=json.loads(record.targets_json),
        riskReward=None,  # never computed in this release - see BUILD_SPEC.md scope
        coreSignal=[StructureRefOut(**r) for r in json.loads(record.core_signal_json)],
        confirmations=[StructureRefOut(**r) for r in json.loads(record.confirmations_json)],
        conflicts=[StructureRefOut(**r) for r in json.loads(record.conflicts_json)],
        reasoningChain=json.loads(record.reasoning_chain_json),
        dataQuality=record.data_quality,
        decision=record.decision,
    )


@app.get("/api/signals", response_model=List[SignalOut])
def list_all_signals():
    conn = get_conn()
    try:
        return [_record_to_out(r) for r in database.list_signals(conn)]
    finally:
        conn.close()


@app.get("/api/signals/active", response_model=List[SignalOut])
def list_active_signals():
    conn = get_conn()
    try:
        return [_record_to_out(r) for r in database.list_signals(conn, states=ACTIVE_STATES)]
    finally:
        conn.close()


@app.get("/api/signals/resolved", response_model=List[SignalOut])
def list_resolved_signals():
    conn = get_conn()
    try:
        return [_record_to_out(r) for r in database.list_signals(conn, states=RESOLVED_STATES)]
    finally:
        conn.close()


@app.get("/api/signals/{signal_id}", response_model=SignalOut)
def get_signal(signal_id: int):
    conn = get_conn()
    try:
        record = database.get_signal(conn, signal_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Signal not found")
        return _record_to_out(record)
    finally:
        conn.close()


@app.get("/api/system-health", response_model=SystemHealthOut)
def system_health():
    conn = get_conn()
    try:
        heartbeats = database.list_heartbeats(conn)
    finally:
        conn.close()

    telegram_configured = TelegramNotifier().is_configured()

    if not heartbeats:
        return SystemHealthOut(
            dataFeedConnected=False, lastTickAt=None, telegramConfigured=telegram_configured, automationEnabled=False
        )

    latest = max(heartbeats, key=lambda h: h["last_bar_time"])
    now = datetime.now(latest["last_bar_time"].tzinfo)
    age_seconds = (now - latest["last_bar_time"]).total_seconds()
    connected = age_seconds <= HEARTBEAT_STALE_SECONDS

    return SystemHealthOut(
        dataFeedConnected=connected,
        lastTickAt=latest["last_bar_time"].isoformat(),
        telegramConfigured=telegram_configured,
        automationEnabled=False,
    )
