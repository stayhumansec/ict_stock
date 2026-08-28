"""Signal dataclass and state machine.

A Signal is the system's structured output for a potential setup — never a
probability, never a guarantee. `confluence_summary` (once a confluence
scorer exists — out of scope for this release) is a structured breakdown
of which conditions were met, not a win-probability number.

"No Trade" / "No Setup" is a valid, normal outcome: nothing here forces a
Signal to be created just because bars are ticking by.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from backend.smc.models import Direction

from .mode import MethodologyMode


class SignalState(str, Enum):
    DEVELOPING = "DEVELOPING"   # candidate setup identified, confluence not yet confirmed
    CONFIRMED = "CONFIRMED"     # confluence conditions met, awaiting entry trigger
    TRIGGERED = "TRIGGERED"     # entry condition hit (manual execution happens outside this system)
    INVALIDATED = "INVALIDATED"  # setup invalidated before/after triggering
    EXPIRED = "EXPIRED"         # setup timed out without confirming/triggering


# Allowed transitions. Anything not listed here is rejected — the state
# machine should never silently accept an invalid jump (e.g. EXPIRED back
# to DEVELOPING).
_ALLOWED_TRANSITIONS: Dict[SignalState, set] = {
    SignalState.DEVELOPING: {SignalState.CONFIRMED, SignalState.INVALIDATED, SignalState.EXPIRED},
    SignalState.CONFIRMED: {SignalState.TRIGGERED, SignalState.INVALIDATED, SignalState.EXPIRED},
    SignalState.TRIGGERED: {SignalState.INVALIDATED},  # e.g. stopped out immediately / structure failed post-entry
    SignalState.INVALIDATED: set(),
    SignalState.EXPIRED: set(),
}

TERMINAL_STATES = {SignalState.INVALIDATED, SignalState.EXPIRED, SignalState.TRIGGERED}


@dataclass
class SignalStateChange:
    from_state: SignalState
    to_state: SignalState
    at_index: int
    reason: str = ""


@dataclass
class Signal:
    signal_id: int
    instrument: str  # e.g. "NIFTY", "BANKNIFTY"
    mode: MethodologyMode
    direction: Direction
    created_index: int
    created_at: datetime
    state: SignalState = SignalState.DEVELOPING

    # Structured evidence backing this signal - references into EngineResult,
    # never copies of the underlying data.
    structure_event_ids: List[int] = field(default_factory=list)
    zone_ids: List[int] = field(default_factory=list)
    sweep_ids: List[int] = field(default_factory=list)

    entry_zone: Optional[tuple] = None  # (low, high)
    stop_loss: Optional[float] = None
    targets: List[float] = field(default_factory=list)

    # Structured summary only - never a probability. Populated by a future
    # confluence scorer; left None until that exists.
    confluence_summary: Optional[Dict] = None

    notes: str = ""
    history: List[SignalStateChange] = field(default_factory=list)

    def transition(self, to_state: SignalState, at_index: int, reason: str = "") -> None:
        if self.state in TERMINAL_STATES:
            raise ValueError(f"Signal {self.signal_id} is in terminal state {self.state}, cannot transition further")
        if to_state not in _ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"Invalid signal transition: {self.state} -> {to_state}")
        self.history.append(SignalStateChange(self.state, to_state, at_index, reason))
        self.state = to_state

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES
