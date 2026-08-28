from datetime import datetime, timedelta, timezone

from backend.smc.config import SMCConfig
from backend.smc.models import Bar, Direction
from backend.smc.displacement import detect_displacement

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_bars(values):
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, (o, h, l, c) in enumerate(values):
        bars.append(
            Bar(index=i, timestamp=start + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=1000)
        )
    return bars


def test_no_displacement_in_quiet_market():
    values = [(100 + i * 0.1, 100.5 + i * 0.1, 99.5 + i * 0.1, 100.2 + i * 0.1) for i in range(20)]
    bars = make_bars(values)
    config = SMCConfig()
    events = detect_displacement(bars, config)
    assert events == []


def test_bullish_displacement_bar_detected():
    quiet = [(100, 100.5, 99.5, 100.2) for _ in range(14)]
    quiet_bars = make_bars(quiet)
    # append a big expansion bar closing near the top
    big = (100, 115, 99, 114)
    bars = make_bars(quiet + [big])
    config = SMCConfig(displacement_atr_multiple=1.5, displacement_close_pct=0.25)
    events = detect_displacement(bars, config)
    assert len(events) == 1
    assert events[0].index == 14
    assert events[0].direction == Direction.BULLISH


def test_bearish_displacement_bar_detected():
    quiet = [(100, 100.5, 99.5, 100.2) for _ in range(14)]
    big = (100, 101, 85, 86)
    bars = make_bars(quiet + [big])
    config = SMCConfig(displacement_atr_multiple=1.5, displacement_close_pct=0.25)
    events = detect_displacement(bars, config)
    assert len(events) == 1
    assert events[0].direction == Direction.BEARISH


def test_large_range_but_close_in_middle_is_not_displacement():
    quiet = [(100, 100.5, 99.5, 100.2) for _ in range(14)]
    # big range but closes dead in the middle -> not a directional displacement
    big = (100, 115, 85, 100)
    bars = make_bars(quiet + [big])
    config = SMCConfig(displacement_atr_multiple=1.5, displacement_close_pct=0.25)
    events = detect_displacement(bars, config)
    assert events == []


def test_no_repainting_atr_only_uses_past_and_current_bar():
    # A displacement flag at index i must not depend on any bar after i.
    quiet = [(100, 100.5, 99.5, 100.2) for _ in range(14)]
    big = (100, 115, 99, 114)
    trailing_calm = [(114, 114.5, 113.5, 114.2) for _ in range(5)]
    full = make_bars(quiet + [big] + trailing_calm)
    truncated = make_bars(quiet + [big])
    config = SMCConfig(displacement_atr_multiple=1.5, displacement_close_pct=0.25)

    full_events = [e for e in detect_displacement(full, config) if e.index == 14]
    truncated_events = detect_displacement(truncated, config)
    assert full_events == truncated_events
