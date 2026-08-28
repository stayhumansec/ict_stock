from datetime import datetime, timedelta, timezone

from backend.smc.config import SMCConfig
from backend.smc.models import (
    Bar,
    Direction,
    LiquidityPool,
    PoolState,
    PoolType,
    StructureEvent,
    StructureEventType,
    SweepFollowThrough,
)
from backend.smc.liquidity import (
    build_swing_pools,
    resolve_sweep_follow_through,
    update_pool_states_and_detect_sweeps,
)
from backend.smc.swings import detect_swings

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_bars(values):
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, (o, h, l, c) in enumerate(values):
        bars.append(
            Bar(index=i, timestamp=start + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=1000)
        )
    return bars


def test_pool_sweeps_on_wick_even_if_close_does_not_break_it():
    # Pool at price 110 (a swing high). A later bar wicks to 112 (through
    # the pool) but closes back at 108 (below it) - the pool must still
    # flip to SWEPT because sweeps are wick-based, not close-based.
    pool = LiquidityPool(pool_type=PoolType.SWING_HIGH, price=110, formed_index=0)
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (100, 105, 99, 104),
            (104, 112, 103, 108),  # wicks through 110, closes at 108
        ]
    )
    sweeps = update_pool_states_and_detect_sweeps(bars, [pool])
    assert pool.state == PoolState.SWEPT
    assert pool.swept_index == 2
    assert len(sweeps) == 1
    assert sweeps[0].rejection is True  # closed back inside (108 < 110)
    assert sweeps[0].direction == Direction.BEARISH


def test_pool_not_swept_by_close_alone_without_wick_through():
    # Sanity: a pool must not appear swept just because we constructed it
    # oddly - only genuine high/low breach counts.
    pool = LiquidityPool(pool_type=PoolType.SWING_HIGH, price=110, formed_index=0)
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (100, 105, 99, 104),
            (104, 109, 103, 105),  # high=109 < 110, never trades through
        ]
    )
    sweeps = update_pool_states_and_detect_sweeps(bars, [pool])
    assert pool.state != PoolState.SWEPT
    assert sweeps == []


def test_pool_tested_before_swept():
    pool = LiquidityPool(pool_type=PoolType.SWING_LOW, price=90, formed_index=0)
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (95, 96, 90, 95),   # touches exactly 90 (low==90) -> TESTED, not swept (not <90)
            (95, 96, 89, 90),   # trades through (low=89<90) -> SWEPT
        ]
    )
    # process bar-by-bar-ish: call once, function walks internally
    sweeps = update_pool_states_and_detect_sweeps(bars, [pool])
    assert pool.state == PoolState.SWEPT
    assert pool.swept_index == 2


def test_pool_stays_swept_permanently():
    pool = LiquidityPool(pool_type=PoolType.SWING_HIGH, price=110, formed_index=0)
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (100, 115, 99, 104),  # sweeps at bar1 (high 115>110)
            (100, 103, 98, 99),   # price comes back below - pool must remain SWEPT
        ]
    )
    update_pool_states_and_detect_sweeps(bars, [pool])
    assert pool.state == PoolState.SWEPT
    assert pool.swept_index == 1


def test_sweep_without_rejection_is_no_followthrough():
    pool = LiquidityPool(pool_type=PoolType.SWING_HIGH, price=110, formed_index=0)
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (100, 115, 99, 114),  # sweeps and closes ABOVE 110 -> no rejection
        ]
    )
    sweeps = update_pool_states_and_detect_sweeps(bars, [pool])
    resolve_sweep_follow_through(sweeps, structure_events=[])
    assert sweeps[0].rejection is False
    assert sweeps[0].follow_through == SweepFollowThrough.SWEPT_NO_FOLLOWTHROUGH


def test_sweep_with_rejection_and_opposite_choch_is_confirmed_reversal():
    pool = LiquidityPool(pool_type=PoolType.SWING_HIGH, price=110, formed_index=0)
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (104, 112, 103, 108),  # bar1: sweeps high, rejects (close 108<110) -> BEARISH sweep
            (108, 109, 105, 106),
        ]
    )
    sweeps = update_pool_states_and_detect_sweeps(bars, [pool])
    assert sweeps[0].direction == Direction.BEARISH

    choch = StructureEvent(
        event_type=StructureEventType.CHOCH,
        direction=Direction.BEARISH,
        confirmed_index=2,
        reference_price=100,
        series="internal",
        event_id=0,
    )
    resolve_sweep_follow_through(sweeps, structure_events=[choch])
    assert sweeps[0].follow_through == SweepFollowThrough.CONFIRMED_REVERSAL
    assert sweeps[0].resolving_structure_event_id == 0


def test_sweep_with_rejection_but_no_opposite_structure_is_no_followthrough():
    pool = LiquidityPool(pool_type=PoolType.SWING_HIGH, price=110, formed_index=0)
    bars = make_bars(
        [
            (100, 101, 99, 100),
            (104, 112, 103, 108),  # rejection sweep
            (108, 109, 105, 106),
        ]
    )
    sweeps = update_pool_states_and_detect_sweeps(bars, [pool])
    resolve_sweep_follow_through(sweeps, structure_events=[])
    assert sweeps[0].follow_through == SweepFollowThrough.SWEPT_NO_FOLLOWTHROUGH


def test_build_swing_pools_one_per_confirmed_swing():
    values = [
        (100, 101, 99, 100),
        (100, 102, 100, 101),
        (101, 108, 100, 107),
        (105, 106, 104, 105),
        (105, 106, 95, 96),
    ]
    bars = make_bars(values)
    swings = detect_swings(bars, n=2, series="internal")
    pools = build_swing_pools(swings)
    assert len(pools) == len(swings)
    types = {p.pool_type for p in pools}
    assert types <= {PoolType.SWING_HIGH, PoolType.SWING_LOW}
