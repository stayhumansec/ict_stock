"""All SMC engine thresholds, expressed as configuration — never hardcoded
inline in detection modules. Every value here should be traceable to a
rule in BUILD_SPEC.md.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SMCConfig:
    # --- Swings (swings.py) ---
    internal_swing_n: int = 2       # bars each side, internal/LTF structure
    external_swing_n: int = 8       # bars each side, external/HTF structure

    # --- Liquidity pools (liquidity.py) ---
    equal_level_atr_multiple: float = 0.05   # tolerance band for equal highs/lows, x ATR
    atr_period: int = 14

    # --- Displacement (displacement.py) ---
    displacement_atr_multiple: float = 1.5   # bar range must exceed this x ATR
    displacement_close_pct: float = 0.25     # close must sit within this % of range extreme

    # --- Order blocks (order_blocks.py) ---
    order_block_lookback_bars: int = 10      # max bars to look back for the last opposite candle
                                              # before a displacement leading to BOS/MSS

    # --- Fair Value Gap / Order Block mitigation ---
    partial_mitigation_pct: float = 0.5      # fraction of zone traded into -> PARTIALLY_MITIGATED
    full_mitigation_pct: float = 1.0         # fraction of zone traded into -> FULLY_MITIGATED

    # --- Structure (structure.py) ---
    # A bar close must exceed the reference level by at least this many points
    # (0.0 = any close beyond the level counts). Kept as a config knob for
    # future ablation on noise filtering; spec does not mandate a nonzero
    # value, so it defaults to 0.0 (pure close-beyond-level rule).
    structure_break_min_points: float = 0.0

    def __post_init__(self) -> None:
        if self.internal_swing_n < 1:
            raise ValueError("internal_swing_n must be >= 1")
        if self.external_swing_n < 1:
            raise ValueError("external_swing_n must be >= 1")
        if self.atr_period < 1:
            raise ValueError("atr_period must be >= 1")
        if self.equal_level_atr_multiple <= 0:
            raise ValueError("equal_level_atr_multiple must be > 0")
        if self.displacement_atr_multiple <= 0:
            raise ValueError("displacement_atr_multiple must be > 0")
        if not (0.0 < self.displacement_close_pct <= 0.5):
            raise ValueError("displacement_close_pct must be in (0, 0.5]")
        if self.order_block_lookback_bars < 1:
            raise ValueError("order_block_lookback_bars must be >= 1")
        if not (0.0 < self.partial_mitigation_pct < self.full_mitigation_pct):
            raise ValueError("partial_mitigation_pct must be < full_mitigation_pct")
