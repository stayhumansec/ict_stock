"""Derives a structured confluence summary for a Signal from the real
SMCEngine output that produced it - never from a black-box model, never a
probability. Every field here traces back to an actual detected event.

This is the "future confluence scorer" BUILD_SPEC.md deliberately kept
out of the SMC engine itself (see premium_discount.py's docstring) - it
lives here, one layer up, and its score is explicitly a transparent rule-
based composite, not a prediction.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import List, Optional

from backend.smc.models import Direction, EngineResult, RangeContext, StructureEventType

# Look-back window (in bars) for associating a liquidity sweep with a
# signal - a sweep well before the CHoCH that created the signal isn't
# meaningfully "the reason" for it.
SWEEP_LOOKBACK_BARS = 20


@dataclass(frozen=True)
class StructureRef:
    kind: str
    price: float
    note: str = ""


@dataclass(frozen=True)
class ConfluenceSummary:
    core_signal: List[StructureRef]
    confirmations: List[StructureRef]
    conflicts: List[StructureRef]
    reasoning_chain: List[str]
    score: int
    grade: str
    data_quality: str
    decision: str


def _direction_word(direction: Direction) -> str:
    return "Bullish" if direction == Direction.BULLISH else "Bearish"


def refs_to_json(refs: List[StructureRef]) -> str:
    return json.dumps([asdict(r) for r in refs])


def build_confluence_summary(
    result: EngineResult,
    event_ids: List[int],
    direction: Direction,
    state_is_confirmed: bool,
    risk_gate_allowed: bool,
    data_source: str,
) -> ConfluenceSummary:
    """
    result: the EngineResult from the SMCEngine run at the point this
        summary is (re)computed - always the latest run, so it reflects
        everything known so far without repainting anything already
        emitted (events are only ever appended to, never altered).
    event_ids: the signal's own structure_event_ids (CHoCH, then MSS
        and/or a *_FAILED event once those confirm).
    data_source: "angel_one" or "csv" - drives dataQuality, since a CSV
        replay file has no verified provenance the way a live broker feed
        does.
    """

    own_events = sorted(
        (e for e in result.structure_events if e.event_id in event_ids), key=lambda e: e.confirmed_index
    )
    if not own_events:
        return ConfluenceSummary([], [], [], [], score=0, grade="C", data_quality="LOW", decision="REVIEW")

    choch = next((e for e in own_events if e.event_type == StructureEventType.CHOCH), None)
    mss = next((e for e in own_events if e.event_type == StructureEventType.MSS), None)
    failed = next(
        (e for e in own_events if e.event_type in (StructureEventType.CHOCH_FAILED, StructureEventType.MSS_FAILED)),
        None,
    )

    core_event = mss or choch
    core_signal = [StructureRef(kind=core_event.event_type.value, price=core_event.reference_price)]

    confirmations: List[StructureRef] = []
    if mss and choch:
        confirmations.append(StructureRef(kind=choch.event_type.value, price=choch.reference_price))

    # A displacement bar at the MSS confirmation bar is real, detected
    # evidence - not inferred.
    if mss and any(d.index == mss.confirmed_index and d.direction == direction for d in result.displacement_events):
        confirmations.append(StructureRef(kind="DISPLACEMENT", price=mss.reference_price, note="Displacement confirmed the MSS"))

    # A recent, direction-matching, confirmed-reversal sweep before the
    # CHoCH is real supporting context. Several pools can legitimately get
    # swept in the same window (e.g. a swing low and an equal-lows pool
    # together) - keep only the one nearest the CHoCH so the reasoning
    # chain reads as one coherent story rather than repeating itself.
    anchor_index = choch.confirmed_index if choch else core_event.confirmed_index
    candidate_sweeps = [
        sweep
        for sweep in result.liquidity_sweeps
        if sweep.follow_through.value == "CONFIRMED_REVERSAL"
        and sweep.direction == direction
        and anchor_index - SWEEP_LOOKBACK_BARS <= sweep.swept_index <= anchor_index
    ]
    if candidate_sweeps:
        nearest = max(candidate_sweeps, key=lambda s: s.swept_index)
        confirmations.append(
            StructureRef(kind="SWEEP", price=nearest.swept_price, note=f"{nearest.pool_type.value} swept with rejection")
        )

    conflicts: List[StructureRef] = []
    context_at_core = next((c for c in result.dealing_range_contexts if c.index == core_event.confirmed_index), None)
    if context_at_core:
        opposing = (direction == Direction.BULLISH and context_at_core.context == RangeContext.PREMIUM) or (
            direction == Direction.BEARISH and context_at_core.context == RangeContext.DISCOUNT
        )
        if opposing:
            conflicts.append(
                StructureRef(
                    kind="PREMIUM_DISCOUNT",
                    price=context_at_core.equilibrium,
                    note=f"Price is in {context_at_core.context.value.lower()} of the higher-timeframe range",
                )
            )

    reasoning_chain: List[str] = []
    for ref in confirmations:
        if ref.kind == "SWEEP":
            reasoning_chain.append(ref.note)
    if choch:
        reasoning_chain.append(f"{_direction_word(direction)} CHoCH confirmed at {choch.reference_price:.2f}")
    if mss:
        has_displacement = any(c.kind == "DISPLACEMENT" for c in confirmations)
        reasoning_chain.append(
            f"{_direction_word(direction)} MSS confirmed"
            + (" by displacement" if has_displacement else "")
            + f" at {mss.reference_price:.2f}"
        )
    for ref in conflicts:
        reasoning_chain.append(ref.note)
    if failed:
        reasoning_chain.append(f"{failed.event_type.value} - setup invalidated")

    # Transparent rule-based composite - explicitly not a probability.
    # Capped contributions so no single factor can dominate the range.
    score = 45
    score += 15 * min(len(confirmations), 2)
    score -= 15 * len(conflicts)
    if mss:
        score += 10
    score = max(0, min(100, score))
    grade = "A" if score >= 75 else "B" if score >= 55 else "C"

    data_quality = "HIGH" if data_source == "angel_one" else "MEDIUM"

    decision = "MANUAL_ENTRY" if state_is_confirmed and risk_gate_allowed else "REVIEW"

    return ConfluenceSummary(
        core_signal=core_signal,
        confirmations=confirmations,
        conflicts=conflicts,
        reasoning_chain=reasoning_chain,
        score=score,
        grade=grade,
        data_quality=data_quality,
        decision=decision,
    )
