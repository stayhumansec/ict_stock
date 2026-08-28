"""Structure classification (HH/HL/LH/LL) and BOS/CHoCH/MSS detection.

Everything here is close-based, per BUILD_SPEC.md section 3 — a wick
breaking a level is never sufficient; only `bar.close` is compared against
reference swing prices. Liquidity sweeps (wick-based) live in a separate
module (liquidity.py) and must never be conflated with this one.

Non-repainting: structure events are only emitted at the index of the bar
whose close triggers them, and only reference swings already confirmed as
of that same index (see swings.swings_confirmed_by).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import SMCConfig
from .models import (
    Bar,
    Direction,
    StructureEvent,
    StructureEventType,
    StructureLabel,
    StructureState,
    Swing,
    SwingKind,
)


@dataclass(frozen=True)
class ClassifiedSwing:
    swing: Swing
    label: StructureLabel


def classify_swings(swings: List[Swing]) -> List[ClassifiedSwing]:
    """Label each swing HH/HL/LH/LL relative to the previous swing of the
    same kind, in chronological (confirmed_index) order."""

    ordered = sorted(swings, key=lambda s: (s.confirmed_index, s.formed_index))
    classified: List[ClassifiedSwing] = []
    last_high: Optional[Swing] = None
    last_low: Optional[Swing] = None

    for s in ordered:
        if s.kind == SwingKind.HIGH:
            if last_high is not None:
                label = StructureLabel.HH if s.price > last_high.price else StructureLabel.LH
                classified.append(ClassifiedSwing(s, label))
            last_high = s
        else:
            if last_low is not None:
                label = StructureLabel.HL if s.price > last_low.price else StructureLabel.LL
                classified.append(ClassifiedSwing(s, label))
            last_low = s

    return classified


def current_structure_state(classified: List[ClassifiedSwing]) -> StructureState:
    """Bullish = most recent confirmed pair is HH+HL, Bearish = LL+LH,
    else TRANSITION. Uses the most recent labeled high and low regardless
    of interleaving order, per spec section 2."""

    last_high_label: Optional[StructureLabel] = None
    last_low_label: Optional[StructureLabel] = None
    for cs in classified:
        if cs.swing.kind == SwingKind.HIGH:
            last_high_label = cs.label
        else:
            last_low_label = cs.label

    if last_high_label == StructureLabel.HH and last_low_label == StructureLabel.HL:
        return StructureState.BULLISH
    if last_high_label == StructureLabel.LL and last_low_label == StructureLabel.LH:
        return StructureState.BEARISH
    return StructureState.TRANSITION


@dataclass
class _PendingChoch:
    direction: Direction
    reference_price: float
    event_id: int
    opposite_extreme: float  # the CHoCH bar's opposite extreme, for CHOCH_FAILED check
    reference_swing_formed_index: int


@dataclass
class _PendingMss:
    direction: Direction
    reference_price: float  # the MSS confirmation level (close price of confirming bar)
    event_id: int
    confirmed_index: int


def detect_structure_events(
    bars: List[Bar],
    internal_swings: List[Swing],
    config: SMCConfig,
    displaced_indices: Optional[set] = None,
    series: str = "internal",
) -> List[StructureEvent]:
    """Walk bars chronologically, emitting BOS/CHoCH/CHOCH_FAILED/MSS/MSS_FAILED.

    `displaced_indices` (bar indices flagged by displacement.py as having
    range-expansion in a given direction) is used to confirm MSS — a CHoCH
    alone is never enough. If not supplied, MSS falls back to "a further
    bar closes beyond the CHoCH level" per the spec's alternate MSS clause
    (expansion requirement is simply never satisfied by any index, in which
    case only the plain reference-level-break path can confirm MSS below —
    but since the spec requires displacement *or* a further break-with-
    expansion, we still gate MSS on displaced_indices membership; callers
    who want the engine's own displacement detector wired in should pass it
    through from displacement.py).
    """

    displaced_indices = displaced_indices or set()
    events: List[StructureEvent] = []
    next_event_id = 0

    def new_id() -> int:
        nonlocal next_event_id
        eid = next_event_id
        next_event_id += 1
        return eid

    # Broken reference levels already fired as BOS (keyed by swing
    # formed_index), so a sustained move past the same level doesn't
    # re-fire BOS on every subsequent bar.
    bos_broken_up: set = set()
    bos_broken_down: set = set()

    # Reference swing levels that have already been broken via a
    # CHoCH -> MSS confirmation. Structure classification lags behind an
    # MSS confirmation (no new opposing swing has confirmed yet), so
    # without this a further close beyond the same stale swing level would
    # re-fire a fresh CHoCH against a level the engine already confirmed
    # broken. A CHOCH_FAILED (reclaim) does NOT consume the level - a
    # later break of it is still a fresh, legitimate CHoCH candidate.
    choch_consumed_high: set = set()
    choch_consumed_low: set = set()

    pending_choch: Optional[_PendingChoch] = None
    pending_mss: Optional[_PendingMss] = None  # confirmed MSS awaiting possible MSS_FAILED

    for i, bar in enumerate(bars):
        confirmed = [s for s in internal_swings if s.confirmed_index <= i]
        classified = classify_swings(confirmed)
        state = current_structure_state(classified)

        last_high = next((s for s in reversed(confirmed) if s.kind == SwingKind.HIGH), None)
        last_low = next((s for s in reversed(confirmed) if s.kind == SwingKind.LOW), None)

        # A new CHoCH may only open if none was pending at the *start* of
        # this bar - resolving one (MSS/CHOCH_FAILED) mid-bar must not let
        # a fresh one open in the same iteration.
        choch_was_pending_at_bar_start = pending_choch is not None

        # --- MSS_FAILED: close back through the MSS confirmation level
        # before the next opposing swing confirms. ---
        if pending_mss is not None and i > pending_mss.confirmed_index:
            reverted = (
                bar.close < pending_mss.reference_price
                if pending_mss.direction == Direction.BULLISH
                else bar.close > pending_mss.reference_price
            )
            opposing_swing_confirmed = (
                last_low is not None and last_low.confirmed_index > pending_mss.confirmed_index
                if pending_mss.direction == Direction.BULLISH
                else last_high is not None and last_high.confirmed_index > pending_mss.confirmed_index
            )
            if reverted:
                events.append(
                    StructureEvent(
                        event_type=StructureEventType.MSS_FAILED,
                        direction=pending_mss.direction,
                        confirmed_index=i,
                        reference_price=pending_mss.reference_price,
                        series=series,
                        note="Price closed back through the MSS confirmation level.",
                        related_event_id=pending_mss.event_id,
                        event_id=new_id(),
                    )
                )
                pending_mss = None
            elif opposing_swing_confirmed:
                pending_mss = None  # window for MSS_FAILED has closed

        # --- CHOCH_FAILED: close back beyond the pending CHoCH bar's
        # opposite extreme before MSS confirms. ---
        if pending_choch is not None:
            failed = (
                bar.close > pending_choch.opposite_extreme
                if pending_choch.direction == Direction.BEARISH
                else bar.close < pending_choch.opposite_extreme
            )
            if failed:
                events.append(
                    StructureEvent(
                        event_type=StructureEventType.CHOCH_FAILED,
                        direction=pending_choch.direction,
                        confirmed_index=i,
                        reference_price=pending_choch.reference_price,
                        series=series,
                        note="Price closed back beyond the CHoCH bar's opposite extreme before MSS confirmed.",
                        related_event_id=pending_choch.event_id,
                        event_id=new_id(),
                    )
                )
                pending_choch = None

        # --- MSS confirmation: CHoCH + displacement/expansion in the same
        # direction, or a further close beyond the CHoCH level with range
        # expansion. Never on the CHoCH bar itself. ---
        if pending_choch is not None:
            choch_bar_index = None
            # find the bar index the pending CHoCH was raised on by matching
            # the emitted event (last CHOCH event with this event_id)
            choch_event = next(e for e in events if e.event_id == pending_choch.event_id)
            choch_bar_index = choch_event.confirmed_index

            beyond_level = (
                bar.close > pending_choch.reference_price
                if pending_choch.direction == Direction.BULLISH
                else bar.close < pending_choch.reference_price
            )
            if beyond_level and i in displaced_indices and i != choch_bar_index:
                mss_event_id = new_id()
                events.append(
                    StructureEvent(
                        event_type=StructureEventType.MSS,
                        direction=pending_choch.direction,
                        confirmed_index=i,
                        reference_price=pending_choch.reference_price,
                        series=series,
                        note="CHoCH confirmed by displacement/expansion.",
                        related_event_id=pending_choch.event_id,
                        event_id=mss_event_id,
                    )
                )
                pending_mss = _PendingMss(
                    direction=pending_choch.direction,
                    reference_price=bar.close,
                    event_id=mss_event_id,
                    confirmed_index=i,
                )
                if pending_choch.direction == Direction.BEARISH:
                    choch_consumed_low.add(pending_choch.reference_swing_formed_index)
                else:
                    choch_consumed_high.add(pending_choch.reference_swing_formed_index)
                pending_choch = None

        # --- BOS: continuation in prevailing structure. Fires once per
        # distinct reference level. ---
        if state == StructureState.BULLISH and last_high is not None:
            if (
                bar.close > last_high.price + config.structure_break_min_points
                and last_high.formed_index not in bos_broken_up
            ):
                events.append(
                    StructureEvent(
                        event_type=StructureEventType.BOS,
                        direction=Direction.BULLISH,
                        confirmed_index=i,
                        reference_price=last_high.price,
                        series=series,
                        event_id=new_id(),
                    )
                )
                bos_broken_up.add(last_high.formed_index)
        elif state == StructureState.BEARISH and last_low is not None:
            if (
                bar.close < last_low.price - config.structure_break_min_points
                and last_low.formed_index not in bos_broken_down
            ):
                events.append(
                    StructureEvent(
                        event_type=StructureEventType.BOS,
                        direction=Direction.BEARISH,
                        confirmed_index=i,
                        reference_price=last_low.price,
                        series=series,
                        event_id=new_id(),
                    )
                )
                bos_broken_down.add(last_low.formed_index)

        # --- CHoCH: close against prevailing structure. Only one pending
        # per direction at a time — don't re-fire while one is unresolved. ---
        if not choch_was_pending_at_bar_start:
            if (
                state == StructureState.BULLISH
                and last_low is not None
                and bar.close < last_low.price
                and last_low.formed_index not in choch_consumed_low
            ):
                event_id = new_id()
                events.append(
                    StructureEvent(
                        event_type=StructureEventType.CHOCH,
                        direction=Direction.BEARISH,
                        confirmed_index=i,
                        reference_price=last_low.price,
                        series=series,
                        event_id=event_id,
                    )
                )
                pending_choch = _PendingChoch(
                    direction=Direction.BEARISH,
                    reference_price=last_low.price,
                    event_id=event_id,
                    opposite_extreme=bar.high,
                    reference_swing_formed_index=last_low.formed_index,
                )
            elif (
                state == StructureState.BEARISH
                and last_high is not None
                and bar.close > last_high.price
                and last_high.formed_index not in choch_consumed_high
            ):
                event_id = new_id()
                events.append(
                    StructureEvent(
                        event_type=StructureEventType.CHOCH,
                        direction=Direction.BULLISH,
                        confirmed_index=i,
                        reference_price=last_high.price,
                        series=series,
                        event_id=event_id,
                    )
                )
                pending_choch = _PendingChoch(
                    direction=Direction.BULLISH,
                    reference_price=last_high.price,
                    event_id=event_id,
                    opposite_extreme=bar.low,
                    reference_swing_formed_index=last_high.formed_index,
                )

    return events
