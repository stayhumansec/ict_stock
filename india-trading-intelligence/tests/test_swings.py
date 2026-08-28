from datetime import datetime, timedelta, timezone

from backend.smc.models import Bar, SwingKind
from backend.smc.swings import detect_swings, swings_confirmed_by

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_bars(values):
    """values: list of (open, high, low, close). volume fixed, 5m spacing."""
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, (o, h, l, c) in enumerate(values):
        bars.append(
            Bar(
                index=i,
                timestamp=start + timedelta(minutes=5 * i),
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1000,
            )
        )
    return bars


def test_simple_swing_high_detected_and_confirmed_late():
    # bar 2 is a clean peak with n=2 bars on each side lower.
    values = [
        (100, 101, 99, 100),
        (100, 102, 100, 101),
        (101, 110, 101, 105),  # peak
        (104, 105, 103, 104),
        (103, 104, 102, 103),
    ]
    bars = make_bars(values)
    swings = detect_swings(bars, n=2, series="internal")
    assert len(swings) == 1
    s = swings[0]
    assert s.kind == SwingKind.HIGH
    assert s.formed_index == 2
    assert s.confirmed_index == 4
    assert s.price == 110

    # not knowable before bar 4 closes
    assert swings_confirmed_by(swings, as_of_index=3) == []
    assert swings_confirmed_by(swings, as_of_index=4) == [s]


def test_simple_swing_low_detected():
    values = [
        (100, 101, 99, 100),
        (99, 100, 98, 99),
        (98, 99, 90, 95),  # trough
        (96, 97, 95, 96),
        (97, 98, 96, 97),
    ]
    bars = make_bars(values)
    swings = detect_swings(bars, n=2, series="internal")
    assert len(swings) == 1
    s = swings[0]
    assert s.kind == SwingKind.LOW
    assert s.formed_index == 2
    assert s.price == 90


def test_no_swing_on_monotonic_series():
    values = [(100 + i, 101 + i, 99 + i, 100 + i) for i in range(10)]
    bars = make_bars(values)
    swings = detect_swings(bars, n=2, series="internal")
    assert swings == []


def test_too_short_series_returns_no_swings():
    values = [(100, 101, 99, 100)] * 3
    bars = make_bars(values)
    swings = detect_swings(bars, n=2, series="internal")
    assert swings == []


def test_larger_n_requires_wider_confirmation():
    # peak at index 4, needs n=4 bars each side => requires indices 0..8
    values = [
        (100, 101, 99, 100),
        (100, 102, 100, 101),
        (101, 103, 100, 102),
        (102, 104, 101, 103),
        (103, 120, 102, 110),  # peak
        (109, 110, 107, 108),
        (107, 108, 105, 106),
        (105, 106, 103, 104),
        (103, 104, 101, 102),
    ]
    bars = make_bars(values)
    swings = detect_swings(bars, n=4, series="external")
    assert len(swings) == 1
    assert swings[0].formed_index == 4
    assert swings[0].confirmed_index == 8


def test_equal_highs_do_not_both_qualify_as_swing():
    # a plateau at the peak means neither bar is strictly greater than the
    # other -> no swing high should be flagged for either (strict >).
    values = [
        (100, 101, 99, 100),
        (100, 102, 100, 101),
        (101, 105, 101, 104),
        (104, 105, 103, 104),  # equal high to previous
        (103, 104, 102, 103),
    ]
    bars = make_bars(values)
    swings = detect_swings(bars, n=2, series="internal")
    assert swings == []


def test_invalid_n_raises():
    bars = make_bars([(100, 101, 99, 100)] * 5)
    try:
        detect_swings(bars, n=0, series="internal")
        assert False, "expected ValueError"
    except ValueError:
        pass
