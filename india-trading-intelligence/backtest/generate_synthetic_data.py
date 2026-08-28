"""Generates synthetic OHLCV bars containing a deliberate
sweep -> CHoCH/MSS -> displacement -> retest sequence, purely so the SMC
engine has something structured (but not hand-picked-to-cheat) to run
against without needing a broker connection.

This is explicitly synthetic data for engine sanity-checking — never
fabricated data presented as real market history.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import List

from backend.smc.models import Bar

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def _bar(index: int, timestamp: datetime, o: float, h: float, l: float, c: float, volume: float = 100000) -> Bar:
    h = max(h, o, c)
    l = min(l, o, c)
    return Bar(index=index, timestamp=timestamp, open=o, high=h, low=l, close=c, volume=volume)


def generate_synthetic_bars(seed: int = 42, n_bars: int = 400, base_price: float = 22000.0) -> List[Bar]:
    """Builds a NIFTY-scale 5m bar series: a noisy uptrend establishing
    bullish structure, a liquidity sweep below a prior swing low, a CHoCH,
    a displacement bar confirming MSS, then a retest/continuation leg, all
    embedded in random walk noise before and after so the engine has to
    actually find the sequence rather than seeing only the sequence.
    """

    rng = random.Random(seed)
    start_time = datetime(2024, 6, 3, 9, 15, tzinfo=KOLKATA)  # a Monday

    bars: List[Bar] = []
    price = base_price
    idx = 0

    def add_bar(o: float, h: float, l: float, c: float) -> None:
        nonlocal idx
        ts = start_time + timedelta(minutes=5 * idx)
        bars.append(_bar(idx, ts, o, h, l, c))
        idx += 1

    def random_walk_leg(n: int, drift: float, vol: float) -> None:
        nonlocal price
        for _ in range(n):
            o = price
            c = o + rng.uniform(-vol, vol) + drift
            h = max(o, c) + rng.uniform(0, vol * 0.6)
            l = min(o, c) - rng.uniform(0, vol * 0.6)
            add_bar(o, h, l, c)
            price = c

    # --- Phase 1: noisy uptrend establishing bullish structure ---
    random_walk_leg(n=80, drift=1.2, vol=6.0)

    # --- Phase 2: pullback forming a swing low that will later get swept ---
    swing_low_price = price - 40
    add_bar(price, price + 2, price - 10, price - 8)
    price -= 8
    add_bar(price, price + 3, swing_low_price, swing_low_price + 4)
    price = swing_low_price + 4
    random_walk_leg(n=6, drift=0.3, vol=4.0)

    # --- Phase 3: rally back up, building higher highs/lows (bullish) ---
    random_walk_leg(n=40, drift=1.5, vol=6.0)

    # --- Phase 4: liquidity sweep below the phase-2 swing low (wick-based,
    # rejects back inside range) ---
    sweep_low = swing_low_price - 15
    o = price
    c = price - 5
    add_bar(o, o + 3, sweep_low, c)  # wick sweeps below swing_low_price, closes back above it
    price = c

    # --- Phase 5: CHoCH bar — closes below the prevailing swing low
    # structure (a further bearish close) ---
    random_walk_leg(n=4, drift=-2.0, vol=4.0)

    # --- Phase 6: displacement bar confirming MSS — large range, close
    # near the low of the bar ---
    o = price
    c = price - 120
    h = o + 5
    l = c - 5
    add_bar(o, h, l, c)
    price = c

    # --- Phase 7: retest / continuation leg (drift continues bearish with
    # a shallow retracement back up into the broken zone, then away) ---
    random_walk_leg(n=15, drift=-0.5, vol=5.0)
    random_walk_leg(n=30, drift=-1.0, vol=6.0)

    # --- Phase 8: closing noise so the sequence isn't right at the edge of
    # the series ---
    remaining = max(0, n_bars - len(bars))
    random_walk_leg(n=remaining, drift=0.2, vol=6.0)

    return bars[:n_bars]


if __name__ == "__main__":
    bars = generate_synthetic_bars()
    print(f"Generated {len(bars)} synthetic bars.")
    print(f"First bar: {bars[0]}")
    print(f"Last bar: {bars[-1]}")
