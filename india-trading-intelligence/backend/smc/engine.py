"""SMCEngine — orchestrates every detection module into one EngineResult.

Wiring order matters for non-repainting correctness:
1. Swings (internal + external) — everything else depends on confirmed swings.
2. Displacement — needed by structure.py to confirm MSS.
3. Structure events (BOS/CHoCH/CHOCH_FAILED/MSS/MSS_FAILED) on the internal
   swing series.
4. Liquidity pools + sweeps, then resolve follow-through against the
   structure events just computed.
5. FVGs + mitigation.
6. Order blocks (depend on structure events + displacement) + mitigation +
   breaker reclassification.
7. Premium/discount/equilibrium context, from the external swing series.
"""

from __future__ import annotations

from typing import List

from .config import SMCConfig
from .displacement import detect_displacement, displaced_indices_by_direction
from .fvg import detect_fvgs, update_mitigation
from .liquidity import (
    build_equal_level_pools,
    build_session_and_daily_pools,
    build_swing_pools,
    resolve_sweep_follow_through,
    update_pool_states_and_detect_sweeps,
)
from .models import Bar, EngineResult
from .order_blocks import detect_order_blocks, reclassify_breakers, update_order_block_mitigation
from .premium_discount import compute_dealing_range_contexts
from .structure import detect_structure_events
from .swings import detect_swings


class SMCEngine:
    def __init__(self, config: SMCConfig):
        self.config = config

    def run(self, bars: List[Bar]) -> EngineResult:
        config = self.config

        internal_swings = detect_swings(bars, n=config.internal_swing_n, series="internal")
        external_swings = detect_swings(bars, n=config.external_swing_n, series="external")

        displacement_events = detect_displacement(bars, config)
        displaced_by_dir = displaced_indices_by_direction(displacement_events)
        # structure.py only needs "was this index displaced", direction is
        # implicitly validated by the reference-price-beyond-level check.
        displaced_indices = set(displaced_by_dir.keys())

        structure_events = detect_structure_events(
            bars, internal_swings, config, displaced_indices=displaced_indices, series="internal"
        )

        pools: List = []
        pools.extend(build_swing_pools(internal_swings))
        pools.extend(build_equal_level_pools(internal_swings, bars, config, start_pool_id=len(pools)))
        pools.extend(build_session_and_daily_pools(bars, start_pool_id=len(pools)))

        sweeps = update_pool_states_and_detect_sweeps(bars, pools)
        resolve_sweep_follow_through(sweeps, structure_events)

        fvg_zones = detect_fvgs(bars, config)
        update_mitigation(fvg_zones, bars, config)

        ob_zones = detect_order_blocks(bars, structure_events, displacement_events, config)
        update_order_block_mitigation(ob_zones, bars, config)
        reclassify_breakers(ob_zones, bars, structure_events)

        dealing_range_contexts = compute_dealing_range_contexts(bars, external_swings)

        return EngineResult(
            internal_swings=internal_swings,
            external_swings=external_swings,
            structure_events=structure_events,
            liquidity_pools=pools,
            liquidity_sweeps=sweeps,
            displacement_events=displacement_events,
            zones=fvg_zones + ob_zones,
            dealing_range_contexts=dealing_range_contexts,
        )
