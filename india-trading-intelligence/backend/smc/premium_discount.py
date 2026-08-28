"""Premium / Discount / Equilibrium context relative to the active external
dealing range.

This is continuously recomputed context, not a discrete event — it is
recomputed at every bar from the most recent confirmed *external* swing
high/low pair. It carries no weighting decision of its own; that belongs
to a future confluence scorer.
"""

from __future__ import annotations

from typing import List, Optional

from .models import Bar, DealingRangeContext, RangeContext, Swing, SwingKind


def compute_dealing_range_contexts(bars: List[Bar], external_swings: List[Swing]) -> List[DealingRangeContext]:
    """For every bar index, find the most recent confirmed external swing
    high and swing low (as of that index) and classify the bar's close
    relative to their midpoint (equilibrium). Returns one context per bar
    that actually has both a confirmed high and low to work from — no
    range exists before that."""

    contexts: List[DealingRangeContext] = []
    highs = sorted((s for s in external_swings if s.kind == SwingKind.HIGH), key=lambda s: s.confirmed_index)
    lows = sorted((s for s in external_swings if s.kind == SwingKind.LOW), key=lambda s: s.confirmed_index)

    hi_ptr = 0
    lo_ptr = 0
    last_high: Optional[Swing] = None
    last_low: Optional[Swing] = None

    for i, bar in enumerate(bars):
        while hi_ptr < len(highs) and highs[hi_ptr].confirmed_index <= i:
            last_high = highs[hi_ptr]
            hi_ptr += 1
        while lo_ptr < len(lows) and lows[lo_ptr].confirmed_index <= i:
            last_low = lows[lo_ptr]
            lo_ptr += 1

        if last_high is None or last_low is None or last_high.price <= last_low.price:
            continue

        range_high = last_high.price
        range_low = last_low.price
        equilibrium = (range_high + range_low) / 2.0

        if bar.close > equilibrium:
            context = RangeContext.PREMIUM
        elif bar.close < equilibrium:
            context = RangeContext.DISCOUNT
        else:
            context = RangeContext.EQUILIBRIUM

        contexts.append(
            DealingRangeContext(
                index=i,
                range_high=range_high,
                range_low=range_low,
                equilibrium=equilibrium,
                context=context,
            )
        )

    return contexts
