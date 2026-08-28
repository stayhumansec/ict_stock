"""Fractal-based swing high/low detection.

Non-repainting: a swing formed at bar `i` is only confirmed (returned) once
bar `i + n` has closed, since that is the earliest point at which we know
both sides of the fractal.
"""

from __future__ import annotations

from typing import List

from .models import Bar, Swing, SwingKind


def _is_swing_high(bars: List[Bar], i: int, n: int) -> bool:
    pivot = bars[i].high
    for k in range(1, n + 1):
        if not (pivot > bars[i - k].high and pivot > bars[i + k].high):
            return False
    return True


def _is_swing_low(bars: List[Bar], i: int, n: int) -> bool:
    pivot = bars[i].low
    for k in range(1, n + 1):
        if not (pivot < bars[i - k].low and pivot < bars[i + k].low):
            return False
    return True


def detect_swings(bars: List[Bar], n: int, series: str) -> List[Swing]:
    """Detect confirmed fractal swings over `bars` with `n` bars each side.

    Only bars in `[n, len(bars) - n - 1]` can ever form a swing (both sides
    of the fractal must exist), and the returned Swing's `confirmed_index`
    is `formed_index + n`.
    """

    if n < 1:
        raise ValueError("n must be >= 1")

    swings: List[Swing] = []
    if len(bars) < 2 * n + 1:
        return swings

    for i in range(n, len(bars) - n):
        if _is_swing_high(bars, i, n):
            swings.append(
                Swing(
                    kind=SwingKind.HIGH,
                    formed_index=i,
                    confirmed_index=i + n,
                    price=bars[i].high,
                    n=n,
                    series=series,
                )
            )
        elif _is_swing_low(bars, i, n):
            swings.append(
                Swing(
                    kind=SwingKind.LOW,
                    formed_index=i,
                    confirmed_index=i + n,
                    price=bars[i].low,
                    n=n,
                    series=series,
                )
            )

    return swings


def swings_confirmed_by(swings: List[Swing], as_of_index: int) -> List[Swing]:
    """Filter to swings whose confirmed_index <= as_of_index — the set of
    swings knowable without repainting at a given point in a bar-by-bar
    replay."""

    return [s for s in swings if s.confirmed_index <= as_of_index]
