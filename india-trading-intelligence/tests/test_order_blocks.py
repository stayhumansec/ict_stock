from datetime import datetime, timedelta, timezone

from backend.smc.config import SMCConfig
from backend.smc.models import (
    Bar,
    Direction,
    DisplacementEvent,
    MitigationState,
    StructureEvent,
    StructureEventType,
    ZoneKind,
)
from backend.smc.order_blocks import (
    detect_order_blocks,
    reclassify_breakers,
    update_order_block_mitigation,
)

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_bars(values):
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, (o, h, l, c) in enumerate(values):
        bars.append(
            Bar(index=i, timestamp=start + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=1000)
        )
    return bars


def test_bullish_ob_is_last_bearish_candle_before_displacement_leading_to_bos():
    values = [
        (100, 101, 99, 100),
        (100, 101, 99, 100),
        (102, 103, 98, 99),    # index 2: bearish candle (close<open) -> should become the OB
        (99, 115, 98, 114),    # index 3: displacement bullish bar
        (114, 116, 113, 115),  # index 4: BOS confirming bar, close beyond some ref
    ]
    bars = make_bars(values)
    config = SMCConfig()
    bos = StructureEvent(
        event_type=StructureEventType.BOS,
        direction=Direction.BULLISH,
        confirmed_index=4,
        reference_price=101,
        series="internal",
        event_id=0,
    )
    disp = DisplacementEvent(index=3, direction=Direction.BULLISH, range_=16, atr=2)
    zones = detect_order_blocks(bars, [bos], [disp], config)
    assert len(zones) == 1
    z = zones[0]
    assert z.kind == ZoneKind.ORDER_BLOCK_BULLISH
    assert z.formed_index == 2
    assert z.top == 102     # body_top = max(open,close) = max(102,99)
    assert z.bottom == 99   # body_bottom = min(open,close)
    assert z.confirmed_index == 4
    assert z.related_structure_event_id == 0


def test_no_ob_emitted_without_confirming_structural_event():
    values = [
        (100, 101, 99, 100),
        (102, 103, 98, 99),
        (99, 115, 98, 114),
    ]
    bars = make_bars(values)
    config = SMCConfig()
    disp = DisplacementEvent(index=2, direction=Direction.BULLISH, range_=16, atr=2)
    zones = detect_order_blocks(bars, structure_events=[], displacement_events=[disp], config=config)
    assert zones == []


def test_ob_zone_is_body_not_full_wick_range():
    values = [
        (100, 110, 90, 95),   # index 0: huge wicks, body is [95,100]
        (95, 96, 94, 95),
        (95, 120, 94, 119),   # index 2: displacement
        (119, 121, 118, 120), # index 3: BOS
    ]
    bars = make_bars(values)
    config = SMCConfig()
    bos = StructureEvent(
        event_type=StructureEventType.BOS,
        direction=Direction.BULLISH,
        confirmed_index=3,
        reference_price=101,
        series="internal",
        event_id=0,
    )
    disp = DisplacementEvent(index=2, direction=Direction.BULLISH, range_=26, atr=2)
    zones = detect_order_blocks(bars, [bos], [disp], config)
    assert len(zones) == 1
    assert zones[0].top == 100   # body top, not wick high (110)
    assert zones[0].bottom == 95  # body bottom, not wick low (90)


def test_breaker_reclassification_on_follow_through():
    values = [
        (100, 101, 99, 100),
        (102, 103, 98, 99),    # index 1: bearish candle -> bullish OB body [102,99]
        (99, 115, 98, 114),    # index 2: displacement bullish
        (114, 116, 113, 115),  # index 3: BOS bullish confirms OB
        (115, 116, 90, 91),    # index 4: price crashes back through the OB (fully mitigates, low 90 < bottom 99)
        (91, 92, 85, 86),      # index 5: further bearish BOS/MSS after mitigation -> breaker
    ]
    bars = make_bars(values)
    config = SMCConfig(partial_mitigation_pct=0.5, full_mitigation_pct=1.0)
    bos = StructureEvent(
        event_type=StructureEventType.BOS,
        direction=Direction.BULLISH,
        confirmed_index=3,
        reference_price=101,
        series="internal",
        event_id=0,
    )
    disp = DisplacementEvent(index=2, direction=Direction.BULLISH, range_=16, atr=2)
    zones = detect_order_blocks(bars, [bos], [disp], config)
    update_order_block_mitigation(zones, bars, config)
    assert zones[0].state == MitigationState.FULLY_MITIGATED

    bearish_bos = StructureEvent(
        event_type=StructureEventType.BOS,
        direction=Direction.BEARISH,
        confirmed_index=5,
        reference_price=90,
        series="internal",
        event_id=1,
    )
    reclassify_breakers(zones, bars, [bos, bearish_bos])
    assert zones[0].kind == ZoneKind.BREAKER_BEARISH
    assert zones[0].reclassified_from == ZoneKind.ORDER_BLOCK_BULLISH


def test_ob_invalidated_when_fully_mitigated_without_followthrough():
    values = [
        (100, 101, 99, 100),
        (102, 103, 98, 99),
        (99, 115, 98, 114),
        (114, 116, 113, 115),
        (115, 116, 90, 91),   # fully mitigates OB
        (91, 92, 89, 90),     # no further opposing structural break
    ]
    bars = make_bars(values)
    config = SMCConfig()
    bos = StructureEvent(
        event_type=StructureEventType.BOS,
        direction=Direction.BULLISH,
        confirmed_index=3,
        reference_price=101,
        series="internal",
        event_id=0,
    )
    disp = DisplacementEvent(index=2, direction=Direction.BULLISH, range_=16, atr=2)
    zones = detect_order_blocks(bars, [bos], [disp], config)
    update_order_block_mitigation(zones, bars, config)
    reclassify_breakers(zones, bars, [bos])
    assert zones[0].state == MitigationState.INVALIDATED
    assert zones[0].kind == ZoneKind.ORDER_BLOCK_BULLISH
