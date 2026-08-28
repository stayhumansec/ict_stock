"""Displacement / range-expansion detection.

A bar displaces if its range exceeds `config.displacement_atr_multiple *
ATR[config.atr_period]` and its close sits within `config.displacement_
close_pct` of the top/bottom of that range, in the direction of the move.
Single-bar, non-repainting: only needs the bar itself plus its own ATR
(computed from prior bars), never a future bar.
"""

from __future__ import annotations

from typing import List, Optional

from .config import SMCConfig
from .models import Bar, DisplacementEvent, Direction


def _atr(bars: List[Bar], period: int) -> List[Optional[float]]:
    atrs: List[Optional[float]] = [None] * len(bars)
    trs: List[float] = []
    for i, bar in enumerate(bars):
        if i == 0:
            tr = bar.range
        else:
            prev_close = bars[i - 1].close
            tr = max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))
        trs.append(tr)
        if i >= period - 1:
            atrs[i] = sum(trs[i - period + 1 : i + 1]) / period
    return atrs


def detect_displacement(bars: List[Bar], config: SMCConfig) -> List[DisplacementEvent]:
    """Returns one DisplacementEvent per bar that qualifies. ATR at bar i is
    computed using bars up to and including i (available the instant bar i
    closes), so this never repaints."""

    atrs = _atr(bars, config.atr_period)
    events: List[DisplacementEvent] = []

    for i, bar in enumerate(bars):
        atr = atrs[i]
        if atr is None or atr <= 0:
            continue
        if bar.range <= config.displacement_atr_multiple * atr:
            continue

        top_zone = bar.high - config.displacement_close_pct * bar.range
        bottom_zone = bar.low + config.displacement_close_pct * bar.range

        if bar.close >= top_zone:
            direction = Direction.BULLISH
        elif bar.close <= bottom_zone:
            direction = Direction.BEARISH
        else:
            continue

        events.append(DisplacementEvent(index=i, direction=direction, range_=bar.range, atr=atr))

    return events


def displaced_indices_by_direction(events: List[DisplacementEvent]) -> dict:
    """Convenience: {index: Direction} for O(1) lookups from structure.py."""

    return {e.index: e.direction for e in events}
