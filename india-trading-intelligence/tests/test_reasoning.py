from datetime import datetime, timedelta, timezone

from backend.signals.reasoning import build_confluence_summary
from backend.smc.config import SMCConfig
from backend.smc.engine import SMCEngine
from backend.smc.models import Bar, Direction, StructureEventType

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_bars(values):
    start = datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA)
    bars = []
    for i, (o, h, l, c) in enumerate(values):
        bars.append(
            Bar(index=i, timestamp=start + timedelta(minutes=5 * i), open=o, high=h, low=l, close=c, volume=1000)
        )
    return bars


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


def run_engine(values, config=None):
    bars = make_bars(values)
    return bars, SMCEngine(config or SMCConfig(internal_swing_n=2)).run(bars)


def test_developing_choch_only_summary():
    values = _BULLISH_BASE + [(96, 97, 80, 85)]  # CHoCH bearish
    bars, result = run_engine(values)
    choch = next(e for e in result.structure_events if e.event_type == StructureEventType.CHOCH)

    summary = build_confluence_summary(
        result, event_ids=[choch.event_id], direction=Direction.BEARISH,
        state_is_confirmed=False, risk_gate_allowed=True, data_source="csv",
    )

    assert summary.core_signal[0].kind == "CHOCH"
    assert summary.decision == "REVIEW"
    assert any("CHoCH confirmed" in s for s in summary.reasoning_chain)
    assert summary.data_quality == "MEDIUM"


def test_confirmed_mss_summary_has_higher_score_than_developing():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),
        (85, 86, 83, 84),
        (84, 85, 40, 45),  # MSS confirms
    ]
    bars, result = run_engine(values)
    choch = next(e for e in result.structure_events if e.event_type == StructureEventType.CHOCH)
    mss = next(e for e in result.structure_events if e.event_type == StructureEventType.MSS)

    developing = build_confluence_summary(
        result, event_ids=[choch.event_id], direction=Direction.BEARISH,
        state_is_confirmed=False, risk_gate_allowed=True, data_source="angel_one",
    )
    confirmed = build_confluence_summary(
        result, event_ids=[choch.event_id, mss.event_id], direction=Direction.BEARISH,
        state_is_confirmed=True, risk_gate_allowed=True, data_source="angel_one",
    )

    assert confirmed.score > developing.score
    assert confirmed.core_signal[0].kind == "MSS"
    assert any(c.kind == "CHOCH" for c in confirmed.confirmations)
    assert confirmed.decision == "MANUAL_ENTRY"
    assert confirmed.data_quality == "HIGH"


def test_risk_gate_blocked_forces_review_even_when_confirmed():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),
        (85, 86, 83, 84),
        (84, 85, 40, 45),
    ]
    bars, result = run_engine(values)
    choch = next(e for e in result.structure_events if e.event_type == StructureEventType.CHOCH)
    mss = next(e for e in result.structure_events if e.event_type == StructureEventType.MSS)

    summary = build_confluence_summary(
        result, event_ids=[choch.event_id, mss.event_id], direction=Direction.BEARISH,
        state_is_confirmed=True, risk_gate_allowed=False, data_source="angel_one",
    )
    assert summary.decision == "REVIEW"


def test_failed_event_appears_in_reasoning_chain():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),    # CHoCH
        (85, 105, 84, 102),  # CHOCH_FAILED
    ]
    bars, result = run_engine(values)
    choch = next(e for e in result.structure_events if e.event_type == StructureEventType.CHOCH)
    failed = next(e for e in result.structure_events if e.event_type == StructureEventType.CHOCH_FAILED)

    summary = build_confluence_summary(
        result, event_ids=[choch.event_id, failed.event_id], direction=Direction.BEARISH,
        state_is_confirmed=False, risk_gate_allowed=True, data_source="csv",
    )
    assert any("CHOCH_FAILED" in s for s in summary.reasoning_chain)


def test_empty_event_ids_returns_safe_defaults():
    values = _BULLISH_BASE
    bars, result = run_engine(values)
    summary = build_confluence_summary(
        result, event_ids=[], direction=Direction.BULLISH,
        state_is_confirmed=False, risk_gate_allowed=True, data_source="csv",
    )
    assert summary.core_signal == []
    assert summary.score == 0
    assert summary.grade == "C"


def test_score_is_bounded_0_to_100():
    values = _BULLISH_BASE + [
        (96, 97, 80, 85),
        (85, 86, 83, 84),
        (84, 85, 40, 45),
    ]
    bars, result = run_engine(values)
    choch = next(e for e in result.structure_events if e.event_type == StructureEventType.CHOCH)
    mss = next(e for e in result.structure_events if e.event_type == StructureEventType.MSS)
    summary = build_confluence_summary(
        result, event_ids=[choch.event_id, mss.event_id], direction=Direction.BEARISH,
        state_is_confirmed=True, risk_gate_allowed=True, data_source="angel_one",
    )
    assert 0 <= summary.score <= 100
