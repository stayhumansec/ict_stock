"""Order Block (OB) detection, mitigation, and breaker-block reclassification.

An order block is the last opposite-direction candle before a displacement
move that leads to a confirmed BOS or MSS. The zone is the candle's BODY
(open-to-close), not its full wick range. It is provisional until the
structural event it precedes actually confirms — never emitted before
that confirmation bar has closed.
"""

from __future__ import annotations

from typing import List, Optional

from .config import SMCConfig
from .fvg import update_mitigation
from .models import (
    Bar,
    Direction,
    DisplacementEvent,
    MitigationState,
    StructureEvent,
    StructureEventType,
    Zone,
    ZoneKind,
)


def _find_last_opposite_candle(
    bars: List[Bar], displacement_index: int, direction: Direction, lookback: int
) -> Optional[int]:
    """Scan backward from the bar just before the displacement bar for the
    last candle whose body direction is opposite to `direction`."""

    earliest = max(0, displacement_index - lookback)
    for i in range(displacement_index - 1, earliest - 1, -1):
        bar = bars[i]
        is_bullish_body = bar.close >= bar.open
        if direction == Direction.BULLISH and not is_bullish_body:
            return i
        if direction == Direction.BEARISH and is_bullish_body:
            return i
    return None


def detect_order_blocks(
    bars: List[Bar],
    structure_events: List[StructureEvent],
    displacement_events: List[DisplacementEvent],
    config: SMCConfig,
) -> List[Zone]:
    """For every confirmed BOS/MSS, find the displacement bar(s) preceding
    it in the same direction, then the last opposite candle before that
    displacement — that candle's body is the OB zone. Confirmed (i.e.
    emitted at all) only once the structural event itself has confirmed,
    per the non-repainting rule."""

    zones: List[Zone] = []
    next_id = 0
    displacement_by_index = {d.index: d for d in displacement_events}

    for event in structure_events:
        if event.event_type not in (StructureEventType.BOS, StructureEventType.MSS):
            continue

        # Find the most recent displacement bar at or before the event's
        # confirming bar, matching direction.
        displacement_index = None
        for idx in range(event.confirmed_index, -1, -1):
            d = displacement_by_index.get(idx)
            if d is not None and d.direction == event.direction:
                displacement_index = idx
                break
        if displacement_index is None:
            continue

        ob_index = _find_last_opposite_candle(
            bars, displacement_index, event.direction, config.order_block_lookback_bars
        )
        if ob_index is None:
            continue

        ob_bar = bars[ob_index]
        kind = ZoneKind.ORDER_BLOCK_BULLISH if event.direction == Direction.BULLISH else ZoneKind.ORDER_BLOCK_BEARISH
        zones.append(
            Zone(
                kind=kind,
                top=ob_bar.body_top,
                bottom=ob_bar.body_bottom,
                formed_index=ob_index,
                confirmed_index=event.confirmed_index,
                zone_id=next_id,
                related_structure_event_id=event.event_id,
            )
        )
        next_id += 1

    return zones


def update_order_block_mitigation(zones: List[Zone], bars: List[Bar], config: SMCConfig) -> None:
    update_mitigation(zones, bars, config)


def reclassify_breakers(
    zones: List[Zone], bars: List[Bar], structure_events: List[StructureEvent]
) -> None:
    """If a FULLY_MITIGATED order block is followed by a further structural
    break in the same direction as the mitigation (i.e. price kept going
    the direction that broke the OB), reclassify it as a breaker block
    acting in the opposite role. If fully mitigated with no follow-through
    break, mark it OB_INVALIDATED instead. Mutates zones in place, logging
    the reclassification via `reclassified_from` rather than overwriting
    silently."""

    for zone in zones:
        if zone.kind not in (ZoneKind.ORDER_BLOCK_BULLISH, ZoneKind.ORDER_BLOCK_BEARISH):
            continue
        if zone.state != MitigationState.FULLY_MITIGATED:
            continue
        if zone.last_updated_index is None:
            continue

        # Mitigation of a bullish OB means price broke down through it;
        # follow-through in that (bearish) direction reclassifies it as a
        # bearish breaker. Mirror for bearish OB.
        mitigation_direction = (
            Direction.BEARISH if zone.kind == ZoneKind.ORDER_BLOCK_BULLISH else Direction.BULLISH
        )

        follow_through = any(
            e.direction == mitigation_direction
            and e.confirmed_index > zone.last_updated_index
            and e.event_type in (StructureEventType.BOS, StructureEventType.MSS)
            for e in structure_events
        )

        original_kind = zone.kind
        if follow_through:
            new_kind = ZoneKind.BREAKER_BEARISH if mitigation_direction == Direction.BEARISH else ZoneKind.BREAKER_BULLISH
            zone.kind = new_kind
            zone.reclassified_from = original_kind
        else:
            zone.state = MitigationState.INVALIDATED
