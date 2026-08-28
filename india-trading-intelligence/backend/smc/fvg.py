"""Fair Value Gap (FVG) detection and mitigation tracking.

3-bar pattern, confirmed on close of the third bar — fully non-repainting:
- Bullish FVG: low[i+1] > high[i-1]. Zone = [high[i-1], low[i+1]].
- Bearish FVG: high[i+1] < low[i-1]. Zone = [high[i+1], low[i-1]].

Mitigation state machine: OPEN -> PARTIALLY_MITIGATED -> FULLY_MITIGATED,
based on how much of the zone price has traded back into (wick-based,
matching the liquidity-pool convention of using intrabar extremes).
"""

from __future__ import annotations

from typing import List

from .config import SMCConfig
from .models import Bar, MitigationState, Zone, ZoneKind


def detect_fvgs(bars: List[Bar], config: SMCConfig) -> List[Zone]:
    """Confirmed at the close of bar i+1 (the third bar of the pattern)."""

    zones: List[Zone] = []
    next_id = 0

    for i in range(1, len(bars) - 1):
        prev_bar = bars[i - 1]
        next_bar = bars[i + 1]

        if next_bar.low > prev_bar.high:
            zones.append(
                Zone(
                    kind=ZoneKind.FVG_BULLISH,
                    top=next_bar.low,
                    bottom=prev_bar.high,
                    formed_index=i,
                    confirmed_index=i + 1,
                    zone_id=next_id,
                )
            )
            next_id += 1
        elif next_bar.high < prev_bar.low:
            zones.append(
                Zone(
                    kind=ZoneKind.FVG_BEARISH,
                    top=prev_bar.low,
                    bottom=next_bar.high,
                    formed_index=i,
                    confirmed_index=i + 1,
                    zone_id=next_id,
                )
            )
            next_id += 1

    return zones


def update_mitigation(zones: List[Zone], bars: List[Bar], config: SMCConfig) -> None:
    """Walk bars forward from each zone's confirmed_index and advance its
    mitigation state based on how much of [bottom, top] each bar's
    high/low has traded into. Mutates zones in place. FULLY_MITIGATED is
    terminal (matches the FVG/OB mitigation model — order_blocks.py adds
    the breaker reclassification on top of this for OBs specifically)."""

    for zone in zones:
        height = zone.top - zone.bottom
        if height <= 0:
            continue
        deepest_fraction = 0.0

        for i in range(zone.confirmed_index + 1, len(bars)):
            bar = bars[i]
            overlap_top = min(bar.high, zone.top)
            overlap_bottom = max(bar.low, zone.bottom)
            if overlap_top <= overlap_bottom:
                continue

            if "BULLISH" in zone.kind.value:
                # A bullish zone acts as support/demand and is approached
                # from above; depth is measured from the top downward.
                traded_into = zone.top - overlap_bottom
            else:
                # A bearish zone acts as resistance/supply, approached
                # from below; depth is measured from the bottom upward.
                traded_into = overlap_top - zone.bottom

            fraction = max(0.0, min(1.0, traded_into / height))
            if fraction > deepest_fraction:
                deepest_fraction = fraction
                zone.last_updated_index = i

            if deepest_fraction >= config.full_mitigation_pct:
                zone.state = MitigationState.FULLY_MITIGATED
                break
            elif deepest_fraction >= config.partial_mitigation_pct:
                zone.state = MitigationState.PARTIALLY_MITIGATED
            # else remains OPEN
