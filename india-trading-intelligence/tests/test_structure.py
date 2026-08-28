from datetime import datetime, timedelta, timezone

from backend.smc.config import SMCConfig
from backend.smc.models import Bar, Direction, StructureEventType, StructureLabel, StructureState
from backend.smc.structure import classify_swings, current_structure_state, detect_structure_events
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


def test_classify_hh_hl_sequence_and_bullish_state():
    values = [
        (100, 101, 99, 100),
        (100, 102, 100, 101),
        (101, 108, 100, 107),  # swing high @2 = 108 (H1)
        (105, 106, 104, 105),
        (105, 106, 95, 96),    # swing low @4 = 95 (L1)
        (96, 97, 96, 96),
        (97, 98, 97, 97),
        (97, 100, 96, 99),
        (99, 115, 98, 114),    # swing high @8 = 115 (H2, > H1 -> HH)
        (114, 114, 112, 113),
        (113, 113, 111, 112),
        (111, 112, 105, 106),  # swing low @11 = 105 (L2, > L1 -> HL)
        (106, 107, 106, 106),
        (106, 107, 106, 106),
    ]
    bars = make_bars(values)
    swings = detect_swings(bars, n=2, series="internal")
    classified = classify_swings(swings)
    labels = {(c.swing.formed_index, c.label) for c in classified}
    assert (8, StructureLabel.HH) in labels
    assert (11, StructureLabel.HL) in labels
    assert current_structure_state(classified) == StructureState.BULLISH


# A shared bullish base sequence: swing high @2=102 (H0, unlabeled), swing
# low @4=90 (L0, unlabeled), swing high @7=108 (H1, HH), swing low @10=95
# (L1, HL) -> bullish structure confirmed from bar 12 onward.
_BULLISH_BASE = [
    (100, 101, 99, 100),
    (99, 100, 98, 99),
    (98, 102, 97, 101),
    (101, 101, 96, 97),
    (97, 98, 90, 91),
    (91, 92, 91, 91),
    (92, 95, 92, 94),
    (94, 108, 93, 107),
    (107, 107, 100, 101),
    (101, 102, 100, 101),
    (101, 102, 95, 96),
    (96, 97, 96, 96),
    (96, 97, 96, 96),
]


def test_bos_fires_once_per_level_not_every_bar():
    values = _BULLISH_BASE + [
        (96, 116, 95, 115),   # bar 13: closes above H1 (108) -> BOS
        (115, 120, 114, 119), # bar 14: sustained above -> must NOT re-fire
        (119, 125, 118, 124), # bar 15: still above -> must NOT re-fire
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2)
    swings = detect_swings(bars, n=2, series="internal")
    events = detect_structure_events(bars, swings, config)
    bos_events = [e for e in events if e.event_type == StructureEventType.BOS]
    assert len(bos_events) == 1
    assert bos_events[0].confirmed_index == 13


def test_choch_only_one_pending_per_direction_at_a_time():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),   # bar 13: close 85 < L1(95) -> CHoCH bearish
        (85, 86, 78, 79),   # bar 14: still below -> must NOT re-fire
        (79, 80, 70, 71),   # bar 15: still below -> must NOT re-fire
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2)
    swings = detect_swings(bars, n=2, series="internal")
    events = detect_structure_events(bars, swings, config)
    choch_events = [e for e in events if e.event_type == StructureEventType.CHOCH]
    assert len(choch_events) == 1
    assert choch_events[0].direction == Direction.BEARISH
    assert choch_events[0].confirmed_index == 13


def test_mss_requires_choch_plus_displacement_never_on_choch_bar():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),   # bar 13: CHoCH bearish, ref=95
        (85, 86, 83, 84),   # bar 14: still below, no displacement -> no MSS yet
        (84, 85, 40, 45),   # bar 15: displaced bar closing well below ref -> MSS
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2)
    swings = detect_swings(bars, n=2, series="internal")
    events = detect_structure_events(bars, swings, config, displaced_indices={15})

    choch_events = [e for e in events if e.event_type == StructureEventType.CHOCH]
    mss_events = [e for e in events if e.event_type == StructureEventType.MSS]
    assert len(choch_events) == 1 and choch_events[0].confirmed_index == 13
    assert len(mss_events) == 1 and mss_events[0].confirmed_index == 15
    assert mss_events[0].confirmed_index != choch_events[0].confirmed_index


def test_mss_not_confirmed_without_displacement_flag():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),
        (85, 86, 83, 84),
        (84, 85, 40, 45),  # would confirm MSS if displaced, but we pass no displaced_indices
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2)
    swings = detect_swings(bars, n=2, series="internal")
    events = detect_structure_events(bars, swings, config)  # no displacement info
    mss_events = [e for e in events if e.event_type == StructureEventType.MSS]
    assert mss_events == []


def test_choch_failed_logged_when_price_reclaims_before_mss():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),    # bar 13: CHoCH bearish ref=95, opposite_extreme = bar13.high = 97
        (85, 105, 84, 102),  # bar 14: closes back above 97 -> CHOCH_FAILED
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2)
    swings = detect_swings(bars, n=2, series="internal")
    events = detect_structure_events(bars, swings, config)
    choch_events = [e for e in events if e.event_type == StructureEventType.CHOCH]
    failed = [e for e in events if e.event_type == StructureEventType.CHOCH_FAILED]
    assert len(choch_events) == 1
    assert len(failed) == 1
    assert failed[0].confirmed_index == 14
    assert failed[0].related_event_id == choch_events[0].event_id


def test_mss_failed_when_price_closes_back_through_confirmation_level():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),    # bar 13: CHoCH bearish ref=95
        (85, 86, 83, 84),    # bar 14
        (84, 85, 40, 45),    # bar 15: MSS confirmation, close=45
        (45, 46, 44, 45),    # bar 16
        (45, 100, 44, 90),   # bar 17: closes back through 45 -> MSS_FAILED
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2)
    swings = detect_swings(bars, n=2, series="internal")
    events = detect_structure_events(bars, swings, config, displaced_indices={15})
    mss_events = [e for e in events if e.event_type == StructureEventType.MSS]
    mss_failed = [e for e in events if e.event_type == StructureEventType.MSS_FAILED]
    assert len(mss_events) == 1
    assert len(mss_failed) == 1
    assert mss_failed[0].confirmed_index == 17
    assert mss_failed[0].related_event_id == mss_events[0].event_id


def test_no_spurious_choch_refire_against_already_mss_confirmed_level():
    # Once MSS confirms a break of a swing level, sustained closes beyond
    # that same stale level must not spawn a *new* CHoCH — the engine
    # already confirmed that reversal.
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),   # bar 13: CHoCH bearish ref=95
        (85, 86, 83, 84),   # bar 14
        (84, 85, 40, 45),   # bar 15: MSS confirms, ref=95 consumed
        (45, 46, 30, 31),   # bar 16: still below 95 -> must NOT re-fire CHoCH
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2)
    swings = detect_swings(bars, n=2, series="internal")
    events = detect_structure_events(bars, swings, config, displaced_indices={15})
    choch_events = [e for e in events if e.event_type == StructureEventType.CHOCH]
    assert len(choch_events) == 1


def test_wick_alone_never_triggers_structure_event():
    # A bar that wicks through the swing high but closes back below it must
    # not fire BOS - structure events are close-based only.
    values = [
        (100, 101, 99, 100),
        (100, 102, 100, 101),
        (101, 110, 100, 109),  # swing high @2 = 110
        (109, 110, 108, 109),
        (109, 110, 105, 106),
        (106, 130, 105, 107),  # bar 5: wicks to 130 (>110) but closes at 107 (<110) -> no BOS
    ]
    bars = make_bars(values)
    config = SMCConfig(internal_swing_n=2)
    swings = detect_swings(bars, n=2, series="internal")
    events = detect_structure_events(bars, swings, config)
    bos_events = [e for e in events if e.event_type == StructureEventType.BOS]
    assert bos_events == []
