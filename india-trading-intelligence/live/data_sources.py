"""Bar sources for the live manual runner.

Two sources, both yielding backend.smc.models.Bar one at a time in
chronological order:

- CSV replay: reads a fixed file, for testing the pipeline without a
  broker connection.
- Angel One polling: repeatedly calls get_historical_bars() and yields
  only bars newer than the last one already seen. Polling (not the
  WebSocket tick stream) is used deliberately - turning a raw tick stream
  into clean 5m OHLC bars is a non-trivial aggregation step with its own
  edge cases, and the historical-candle endpoint already gives us
  closed, ready-to-use bars directly.
"""

from __future__ import annotations

import csv
import time
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from backend.brokers.angel_one import AngelOneBroker
from backend.smc.models import Bar

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def _parse_timestamp(raw: str) -> datetime:
    ts = datetime.fromisoformat(raw)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=KOLKATA)
    return ts


def read_csv_bars(path: str) -> list[Bar]:
    """Reads a CSV with header `timestamp,open,high,low,close,volume` into
    a chronologically-ordered list of Bars. Raises on malformed rows
    rather than silently skipping them - a bad row usually means the file
    isn't what you think it is."""

    bars: list[Bar] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must have columns {sorted(required)}, got {reader.fieldnames}")

        for i, row in enumerate(reader):
            bars.append(
                Bar(
                    index=i,
                    timestamp=_parse_timestamp(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )

    bars.sort(key=lambda b: b.timestamp)
    return [
        Bar(index=i, timestamp=b.timestamp, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume)
        for i, b in enumerate(bars)
    ]


def replay_csv_bars(path: str, delay_seconds: float = 0.0) -> Iterator[Bar]:
    """Yields bars from a CSV one at a time, optionally sleeping between
    each to simulate real-time pacing (0 = replay as fast as possible)."""

    for bar in read_csv_bars(path):
        yield bar
        if delay_seconds > 0:
            time.sleep(delay_seconds)


def poll_angel_one_bars(
    broker: AngelOneBroker,
    exchange: str,
    symbol_token: str,
    interval: str,
    poll_seconds: float = 60.0,
    lookback_minutes: int = 60,
    max_polls: Optional[int] = None,
) -> Iterator[Bar]:
    """Polls Angel One's historical-candle endpoint on a fixed interval
    and yields only bars newer than the last one already seen. Runs
    forever unless `max_polls` is set (used by tests).

    This never repaints: only bars strictly after the last-seen timestamp
    are yielded, and Angel One's historical endpoint only returns closed
    candles in the first place.
    """

    last_seen: Optional[datetime] = None
    next_index = 0
    polls = 0

    while max_polls is None or polls < max_polls:
        now = datetime.now(KOLKATA)
        from_dt = now - timedelta(minutes=lookback_minutes)
        raw_bars = broker.get_historical_bars(symbol_token, exchange, interval, from_dt, now)

        new_bars = [b for b in raw_bars if last_seen is None or b.timestamp > last_seen]
        new_bars.sort(key=lambda b: b.timestamp)

        for nb in new_bars:
            yield Bar(
                index=next_index,
                timestamp=nb.timestamp,
                open=nb.open,
                high=nb.high,
                low=nb.low,
                close=nb.close,
                volume=nb.volume,
            )
            next_index += 1
            last_seen = nb.timestamp

        polls += 1
        if max_polls is None or polls < max_polls:
            time.sleep(poll_seconds)
