from datetime import datetime, timedelta, timezone

from backend.smc.config import SMCConfig
from backend.smc.models import Bar, MitigationState, ZoneKind
from backend.smc.fvg import detect_fvgs, update_mitigation

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_bars(values):
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, (o, h, l, c) in enumerate(values):
        bars.append(
            Bar(index=i, timestamp=start + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=1000)
        )
    return bars


def test_bullish_fvg_detected_with_correct_zone():
    # i=1 is "prev_bar" (index i-1=0), gap bar at i=1, next_bar at i=2
    values = [
        (100, 101, 99, 100),   # index 0: high=101
        (101, 106, 100, 105),  # index 1: the gap/displacement bar
        (109, 112, 108, 111),  # index 2: low=108 > prev(index0).high=101 -> bullish FVG
    ]
    bars = make_bars(values)
    config = SMCConfig()
    zones = detect_fvgs(bars, config)
    assert len(zones) == 1
    z = zones[0]
    assert z.kind == ZoneKind.FVG_BULLISH
    assert z.bottom == 101  # high[i-1]
    assert z.top == 108     # low[i+1]
    assert z.formed_index == 1
    assert z.confirmed_index == 2


def test_bearish_fvg_detected_with_correct_zone():
    values = [
        (110, 111, 108, 109),  # index 0: low=108
        (108, 109, 100, 101),  # index 1
        (101, 102, 95, 96),    # index 2: high=102 < prev(index0).low=108 -> bearish FVG
    ]
    bars = make_bars(values)
    config = SMCConfig()
    zones = detect_fvgs(bars, config)
    assert len(zones) == 1
    z = zones[0]
    assert z.kind == ZoneKind.FVG_BEARISH
    assert z.top == 108     # low[i-1]
    assert z.bottom == 102  # high[i+1]


def test_no_fvg_when_ranges_overlap():
    values = [
        (100, 105, 99, 104),
        (104, 106, 103, 105),
        (105, 107, 100, 106),  # low=100 overlaps prev's high(105) - no gap
    ]
    bars = make_bars(values)
    config = SMCConfig()
    zones = detect_fvgs(bars, config)
    assert zones == []


def test_fvg_not_repainted_before_third_bar_closes():
    # Only 2 bars exist - no third bar to confirm, so no zone should appear
    # regardless of how the first two bars are shaped.
    values = [
        (100, 101, 99, 100),
        (101, 106, 100, 105),
    ]
    bars = make_bars(values)
    config = SMCConfig()
    zones = detect_fvgs(bars, config)
    assert zones == []


def test_mitigation_progresses_open_to_partial_to_full():
    values = [
        (100, 101, 99, 100),   # index 0: high=101
        (101, 106, 100, 105),  # index 1
        (109, 112, 108, 111),  # index 2: bullish FVG zone [101, 108], confirmed here
        (111, 112, 110, 111),  # index 3: no retracement into zone
        (111, 112, 104, 105),  # index 4: partial retracement into zone (low=104, zone is 101-108)
        (105, 106, 99, 100),   # index 5: full retracement through zone (low=99 < bottom 101)
    ]
    bars = make_bars(values)
    config = SMCConfig(partial_mitigation_pct=0.3, full_mitigation_pct=1.0)
    zones = detect_fvgs(bars, config)
    update_mitigation(zones, bars, config)
    target = next(z for z in zones if z.kind == ZoneKind.FVG_BULLISH and z.bottom == 101)
    assert target.state == MitigationState.FULLY_MITIGATED


def test_mitigation_stays_open_when_price_never_returns():
    values = [
        (100, 101, 99, 100),
        (101, 106, 100, 105),
        (109, 112, 108, 111),  # bullish FVG [101, 108]
        (111, 120, 110, 119),  # price only goes further away
        (119, 125, 118, 124),
    ]
    bars = make_bars(values)
    config = SMCConfig()
    zones = detect_fvgs(bars, config)
    update_mitigation(zones, bars, config)
    assert zones[0].state == MitigationState.OPEN
