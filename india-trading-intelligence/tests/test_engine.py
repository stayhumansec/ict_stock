from datetime import datetime, timedelta, timezone

from backend.smc.config import SMCConfig
from backend.smc.engine import SMCEngine
from backend.smc.models import Bar, StructureEventType

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_bars(values):
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, (o, h, l, c) in enumerate(values):
        bars.append(
            Bar(index=i, timestamp=start + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=1000)
        )
    return bars


def test_engine_runs_end_to_end_on_a_simple_bullish_sequence():
    values = [
        (100, 101, 99, 100),
        (99, 100, 98, 99),
        (98, 102, 97, 101),   # H0
        (101, 101, 96, 97),
        (97, 98, 90, 91),     # L0
        (91, 92, 91, 91),
        (92, 95, 92, 94),
        (94, 108, 93, 107),   # H1 (HH)
        (107, 107, 100, 101),
        (101, 102, 100, 101),
        (101, 102, 95, 96),   # L1 (HL) -> bullish structure
        (96, 97, 96, 96),
        (96, 97, 96, 96),
        (96, 116, 95, 115),   # BOS bullish
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2, external_swing_n=2)
    result = SMCEngine(config).run(bars)

    assert len(result.internal_swings) > 0
    assert any(e.event_type == StructureEventType.BOS for e in result.structure_events)
    # nothing before it should have fired MSS/CHOCH_FAILED - purely additive sanity check
    assert isinstance(result.liquidity_pools, list)
    assert isinstance(result.zones, list)
    assert isinstance(result.dealing_range_contexts, list)


def test_engine_produces_no_events_on_flat_series():
    bars = make_bars([(100, 100.5, 99.5, 100)] * 30)
    config = SMCConfig()
    result = SMCEngine(config).run(bars)
    assert result.structure_events == []
    assert result.internal_swings == []
