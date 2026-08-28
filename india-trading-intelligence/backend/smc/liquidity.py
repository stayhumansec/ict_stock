"""Liquidity pools and sweeps.

Deliberately separate from structure.py: pools are wick-based
(UNTOUCHED -> TESTED -> SWEPT the instant price *trades through* the level
intrabar, using bar.high/bar.low), never close-based. Structure events are
close-based and live in structure.py — the two must never be conflated.

A sweep alone is not a signal: it becomes candidate reversal evidence only
with (1) rejection (the sweeping bar closes back inside the range) and (2)
a subsequent structure event (CHoCH/MSS) opposite the sweep direction.
Without both, it is logged as SWEPT_NO_FOLLOWTHROUGH.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .config import SMCConfig
from .models import (
    Bar,
    Direction,
    LiquidityPool,
    LiquiditySweep,
    PoolState,
    PoolType,
    StructureEvent,
    Swing,
    SwingKind,
    SweepFollowThrough,
)


def _atr(bars: List[Bar], period: int) -> List[Optional[float]]:
    """Simple ATR (Wilder-free, plain moving average of true range) — index i
    is the ATR available *after* bar i has closed (uses bars[i-period+1..i]
    true ranges plus bar[i-1] close for TR). None until enough bars exist."""

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


def build_swing_pools(swings: List[Swing]) -> List[LiquidityPool]:
    """One raw SWING_HIGH/SWING_LOW pool per confirmed swing."""

    pools: List[LiquidityPool] = []
    for pid, s in enumerate(swings):
        pool_type = PoolType.SWING_HIGH if s.kind == SwingKind.HIGH else PoolType.SWING_LOW
        pools.append(
            LiquidityPool(
                pool_type=pool_type,
                price=s.price,
                formed_index=s.confirmed_index,
                member_indices=(s.formed_index,),
                pool_id=pid,
            )
        )
    return pools


def build_equal_level_pools(
    swings: List[Swing], bars: List[Bar], config: SMCConfig, start_pool_id: int = 0
) -> List[LiquidityPool]:
    """Group swings of the same kind whose prices fall within
    `config.equal_level_atr_multiple * ATR` of each other into equal
    high/low pools. Each pool is only known as of the confirmed_index of
    the swing that completes the pair (i.e. the 2nd+ member's confirmation)."""

    atrs = _atr(bars, config.atr_period)
    pools: List[LiquidityPool] = []
    next_id = start_pool_id

    for kind, pool_type in ((SwingKind.HIGH, PoolType.EQUAL_HIGHS), (SwingKind.LOW, PoolType.EQUAL_LOWS)):
        kind_swings = sorted(
            (s for s in swings if s.kind == kind), key=lambda s: s.confirmed_index
        )
        used = [False] * len(kind_swings)
        for i, s1 in enumerate(kind_swings):
            if used[i]:
                continue
            atr_at = atrs[s1.confirmed_index] if s1.confirmed_index < len(atrs) else None
            if atr_at is None:
                continue
            tolerance = config.equal_level_atr_multiple * atr_at
            group = [s1]
            group_idx = [i]
            for j in range(i + 1, len(kind_swings)):
                if used[j]:
                    continue
                s2 = kind_swings[j]
                if abs(s2.price - s1.price) <= tolerance:
                    group.append(s2)
                    group_idx.append(j)
            if len(group) >= 2:
                for gi in group_idx:
                    used[gi] = True
                avg_price = sum(g.price for g in group) / len(group)
                formed_at = max(g.confirmed_index for g in group)
                pools.append(
                    LiquidityPool(
                        pool_type=pool_type,
                        price=avg_price,
                        formed_index=formed_at,
                        member_indices=tuple(g.formed_index for g in group),
                        pool_id=next_id,
                    )
                )
                next_id += 1

    return pools


def build_session_and_daily_pools(
    bars: List[Bar], start_pool_id: int = 0
) -> List[LiquidityPool]:
    """PREV_DAY_HIGH/LOW, PREV_WEEK_HIGH/LOW, SESSION_HIGH/LOW pools, derived
    from bar timestamps (Asia/Kolkata). A pool becomes knowable only at the
    first bar of the *next* session/day/week, using the prior period's
    actual high/low — never the still-forming current period's."""

    pools: List[LiquidityPool] = []
    next_id = start_pool_id
    if not bars:
        return pools

    def day_key(b: Bar):
        return b.timestamp.date()

    def week_key(b: Bar):
        return b.timestamp.isocalendar()[:2]

    # --- Session (single trading day) pools: emitted as soon as the day
    # changes, referencing the completed prior day's high/low. Also used
    # as SESSION_HIGH/LOW since Release 1 defines one session per day. ---
    current_day = day_key(bars[0])
    day_high = bars[0].high
    day_low = bars[0].low
    day_start_index = 0

    current_week = week_key(bars[0])
    week_high = bars[0].high
    week_low = bars[0].low

    for i in range(1, len(bars)):
        b = bars[i]
        dk = day_key(b)
        wk = week_key(b)

        if dk != current_day:
            pools.append(
                LiquidityPool(
                    pool_type=PoolType.PREV_DAY_HIGH,
                    price=day_high,
                    formed_index=i,
                    member_indices=(day_start_index, i - 1),
                    pool_id=next_id,
                )
            )
            next_id += 1
            pools.append(
                LiquidityPool(
                    pool_type=PoolType.PREV_DAY_LOW,
                    price=day_low,
                    formed_index=i,
                    member_indices=(day_start_index, i - 1),
                    pool_id=next_id,
                )
            )
            next_id += 1
            pools.append(
                LiquidityPool(
                    pool_type=PoolType.SESSION_HIGH,
                    price=day_high,
                    formed_index=i,
                    member_indices=(day_start_index, i - 1),
                    pool_id=next_id,
                )
            )
            next_id += 1
            pools.append(
                LiquidityPool(
                    pool_type=PoolType.SESSION_LOW,
                    price=day_low,
                    formed_index=i,
                    member_indices=(day_start_index, i - 1),
                    pool_id=next_id,
                )
            )
            next_id += 1
            current_day = dk
            day_high = b.high
            day_low = b.low
            day_start_index = i
        else:
            day_high = max(day_high, b.high)
            day_low = min(day_low, b.low)

        if wk != current_week:
            pools.append(
                LiquidityPool(
                    pool_type=PoolType.PREV_WEEK_HIGH,
                    price=week_high,
                    formed_index=i,
                    pool_id=next_id,
                )
            )
            next_id += 1
            pools.append(
                LiquidityPool(
                    pool_type=PoolType.PREV_WEEK_LOW,
                    price=week_low,
                    formed_index=i,
                    pool_id=next_id,
                )
            )
            next_id += 1
            current_week = wk
            week_high = b.high
            week_low = b.low
        else:
            week_high = max(week_high, b.high)
            week_low = min(week_low, b.low)

    return pools


def _is_high_pool(pool_type: PoolType) -> bool:
    return pool_type in (
        PoolType.EQUAL_HIGHS,
        PoolType.PREV_DAY_HIGH,
        PoolType.PREV_WEEK_HIGH,
        PoolType.SESSION_HIGH,
        PoolType.SWING_HIGH,
    )


def update_pool_states_and_detect_sweeps(
    bars: List[Bar], pools: List[LiquidityPool]
) -> List[LiquiditySweep]:
    """Advance each pool's UNTOUCHED -> TESTED -> SWEPT state machine
    bar-by-bar using intrabar high/low (wick-based, never close). Once
    SWEPT, a pool stays swept permanently. Returns one LiquiditySweep per
    pool the instant it flips to SWEPT, flagging rejection if that same bar
    closes back inside the range.
    """

    sweeps: List[LiquiditySweep] = []
    next_sweep_id = 0

    for pool in pools:
        for i in range(pool.formed_index, len(bars)):
            bar = bars[i]
            if pool.state == PoolState.SWEPT:
                break

            is_high = _is_high_pool(pool.pool_type)
            traded_through = bar.high > pool.price if is_high else bar.low < pool.price
            touched = bar.high >= pool.price >= bar.low

            if traded_through:
                pool.state = PoolState.SWEPT
                pool.swept_index = i
                rejection = bar.close < pool.price if is_high else bar.close > pool.price
                direction = Direction.BEARISH if is_high else Direction.BULLISH
                sweeps.append(
                    LiquiditySweep(
                        pool_id=pool.pool_id,
                        pool_type=pool.pool_type,
                        direction=direction,
                        swept_index=i,
                        swept_price=pool.price,
                        rejection=rejection,
                        sweep_id=next_sweep_id,
                    )
                )
                next_sweep_id += 1
            elif touched and pool.state == PoolState.UNTOUCHED:
                pool.state = PoolState.TESTED

    return sweeps


def resolve_sweep_follow_through(
    sweeps: List[LiquiditySweep],
    structure_events: List[StructureEvent],
    max_bars_lookahead: Optional[int] = None,
) -> None:
    """For each sweep with `rejection=True`, look for the next structure
    event (CHoCH or MSS) opposite the sweep direction after the sweep bar.
    If found, mark CONFIRMED_REVERSAL; otherwise SWEPT_NO_FOLLOWTHROUGH.
    Sweeps without rejection are always SWEPT_NO_FOLLOWTHROUGH — a sweep
    alone, even with a later opposite structure event, is not enough
    without the rejection close.
    Mutates `sweeps` in place.
    """

    from .models import StructureEventType  # local import to avoid cycle noise

    for sweep in sweeps:
        if not sweep.rejection:
            sweep.follow_through = SweepFollowThrough.SWEPT_NO_FOLLOWTHROUGH
            continue

        # sweep.direction already encodes the expected reversal direction
        # (BEARISH sweep = swept a high, expecting a bearish reversal).
        expected_direction = sweep.direction

        found = None
        for ev in structure_events:
            if ev.confirmed_index <= sweep.swept_index:
                continue
            if max_bars_lookahead is not None and ev.confirmed_index - sweep.swept_index > max_bars_lookahead:
                continue
            if ev.event_type in (StructureEventType.CHOCH, StructureEventType.MSS) and ev.direction == expected_direction:
                found = ev
                break

        sweep.follow_through = (
            SweepFollowThrough.CONFIRMED_REVERSAL if found is not None else SweepFollowThrough.SWEPT_NO_FOLLOWTHROUGH
        )
        if found is not None:
            sweep.resolving_structure_event_id = found.event_id
