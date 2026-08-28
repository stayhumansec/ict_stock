from datetime import datetime, timedelta, timezone

import pytest

from backend.smc.models import Direction
from backend.signals.mode import ENABLED_MODES, MethodologyMode, is_mode_enabled
from backend.signals.signal import Signal, SignalState

KOLKATA = timezone(timedelta(hours=5, minutes=30))


def make_signal(state: SignalState = SignalState.DEVELOPING) -> Signal:
    return Signal(
        signal_id=1,
        instrument="NIFTY",
        mode=MethodologyMode.SMC,
        direction=Direction.BULLISH,
        created_index=10,
        created_at=datetime(2024, 1, 1, 9, 15, tzinfo=KOLKATA),
        state=state,
    )


def test_only_smc_mode_enabled():
    assert is_mode_enabled(MethodologyMode.SMC) is True
    assert is_mode_enabled(MethodologyMode.ICT) is False
    assert is_mode_enabled(MethodologyMode.HYBRID) is False
    assert ENABLED_MODES == {MethodologyMode.SMC}


def test_valid_transition_developing_to_confirmed():
    s = make_signal()
    s.transition(SignalState.CONFIRMED, at_index=12, reason="confluence met")
    assert s.state == SignalState.CONFIRMED
    assert len(s.history) == 1
    assert s.history[0].from_state == SignalState.DEVELOPING
    assert s.history[0].to_state == SignalState.CONFIRMED


def test_full_lifecycle_developing_confirmed_triggered():
    s = make_signal()
    s.transition(SignalState.CONFIRMED, at_index=12)
    s.transition(SignalState.TRIGGERED, at_index=15)
    assert s.state == SignalState.TRIGGERED
    assert s.is_terminal() is True


def test_invalid_transition_raises():
    s = make_signal()
    with pytest.raises(ValueError):
        s.transition(SignalState.TRIGGERED, at_index=12)  # cannot skip CONFIRMED


def test_cannot_transition_out_of_terminal_state():
    s = make_signal(state=SignalState.EXPIRED)
    with pytest.raises(ValueError):
        s.transition(SignalState.DEVELOPING, at_index=20)


def test_developing_can_expire_without_confirming():
    s = make_signal()
    s.transition(SignalState.EXPIRED, at_index=50, reason="no confirmation within window")
    assert s.state == SignalState.EXPIRED
    assert s.is_terminal() is True


def test_confluence_summary_defaults_to_none_never_fabricated():
    s = make_signal()
    assert s.confluence_summary is None
