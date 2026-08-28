from datetime import datetime, timedelta, timezone

from backend.smc.models import Bar, RangeContext, Swing, SwingKind
from backend.smc.premium_discount import compute_dealing_range_contexts

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_bars(closes):
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, c in enumerate(closes):
        bars.append(
            Bar(index=i, timestamp=start + timedelta(minutes=5 * i), open=c, high=c + 1, low=c - 1, close=c, volume=1000)
        )
    return bars


def test_no_context_before_both_swings_confirmed():
    bars = make_bars([100] * 5)
    high = Swing(kind=SwingKind.HIGH, formed_index=1, confirmed_index=3, price=110, n=1, series="external")
    contexts = compute_dealing_range_contexts(bars, [high])
    assert contexts == []


def test_premium_above_equilibrium_discount_below():
    bars = make_bars([100, 105, 115, 90, 100])
    high = Swing(kind=SwingKind.HIGH, formed_index=0, confirmed_index=0, price=110, n=1, series="external")
    low = Swing(kind=SwingKind.LOW, formed_index=0, confirmed_index=0, price=90, n=1, series="external")
    contexts = compute_dealing_range_contexts(bars, [high, low])
    by_index = {c.index: c for c in contexts}
    assert by_index[0].equilibrium == 100
    assert by_index[1].context == RangeContext.PREMIUM   # close 105 > 100
    assert by_index[2].context == RangeContext.PREMIUM   # close 115 > 100
    assert by_index[3].context == RangeContext.DISCOUNT  # close 90 < 100
    assert by_index[4].context == RangeContext.EQUILIBRIUM  # close 100 == 100


def test_range_updates_when_new_external_swing_confirms():
    bars = make_bars([100, 100, 100, 100, 100, 100])
    high1 = Swing(kind=SwingKind.HIGH, formed_index=0, confirmed_index=0, price=110, n=1, series="external")
    low1 = Swing(kind=SwingKind.LOW, formed_index=0, confirmed_index=0, price=90, n=1, series="external")
    high2 = Swing(kind=SwingKind.HIGH, formed_index=3, confirmed_index=4, price=130, n=1, series="external")
    contexts = compute_dealing_range_contexts(bars, [high1, low1, high2])
    by_index = {c.index: c for c in contexts}
    assert by_index[0].range_high == 110
    assert by_index[3].range_high == 110  # not yet confirmed
    assert by_index[4].range_high == 130  # new external high now active
