"""Core dataclasses shared across the SMC engine.

All timestamps are timezone-aware and expressed in Asia/Kolkata. Nothing in
this module performs detection logic — it only defines the shapes that
`swings.py`, `structure.py`, `liquidity.py`, `displacement.py`, `fvg.py`,
`order_blocks.py`, and `premium_discount.py` operate on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


@dataclass(frozen=True)
class Bar:
    """A single normalized OHLCV candle."""

    index: int
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.high < self.low:
            raise ValueError(f"Bar {self.index}: high < low")
        if not (self.low <= self.open <= self.high):
            raise ValueError(f"Bar {self.index}: open outside high/low range")
        if not (self.low <= self.close <= self.high):
            raise ValueError(f"Bar {self.index}: close outside high/low range")

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def bullish(self) -> bool:
        return self.close >= self.open

    @property
    def body_top(self) -> float:
        return max(self.open, self.close)

    @property
    def body_bottom(self) -> float:
        return min(self.open, self.close)


class SwingKind(str, Enum):
    HIGH = "HIGH"
    LOW = "LOW"


@dataclass(frozen=True)
class Swing:
    """A confirmed fractal swing point.

    `formed_index` is the bar the extreme occurred on; `confirmed_index`
    is `formed_index + n` — the first index at which this swing is knowable
    without repainting. Detection code must never expose a Swing before
    `confirmed_index` has actually closed.
    """

    kind: SwingKind
    formed_index: int
    confirmed_index: int
    price: float
    n: int
    series: str  # "internal" or "external"


class StructureLabel(str, Enum):
    HH = "HH"
    HL = "HL"
    LH = "LH"
    LL = "LL"


class StructureState(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    TRANSITION = "TRANSITION"


class StructureEventType(str, Enum):
    BOS = "BOS"
    CHOCH = "CHOCH"
    CHOCH_FAILED = "CHOCH_FAILED"
    MSS = "MSS"
    MSS_FAILED = "MSS_FAILED"


@dataclass(frozen=True)
class StructureEvent:
    """A BOS/CHoCH/MSS event, confirmed strictly on a bar close."""

    event_type: StructureEventType
    direction: Direction
    confirmed_index: int
    reference_price: float
    series: str
    note: str = ""
    related_event_id: Optional[int] = None
    event_id: int = -1


class PoolType(str, Enum):
    EQUAL_HIGHS = "EQUAL_HIGHS"
    EQUAL_LOWS = "EQUAL_LOWS"
    PREV_DAY_HIGH = "PREV_DAY_HIGH"
    PREV_DAY_LOW = "PREV_DAY_LOW"
    PREV_WEEK_HIGH = "PREV_WEEK_HIGH"
    PREV_WEEK_LOW = "PREV_WEEK_LOW"
    SESSION_HIGH = "SESSION_HIGH"
    SESSION_LOW = "SESSION_LOW"
    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"


class PoolState(str, Enum):
    UNTOUCHED = "UNTOUCHED"
    TESTED = "TESTED"
    SWEPT = "SWEPT"


@dataclass
class LiquidityPool:
    """A liquidity pool tracked through UNTOUCHED -> TESTED -> SWEPT."""

    pool_type: PoolType
    price: float
    formed_index: int
    state: PoolState = PoolState.UNTOUCHED
    swept_index: Optional[int] = None
    member_indices: tuple = field(default_factory=tuple)
    pool_id: int = -1


class SweepFollowThrough(str, Enum):
    PENDING = "PENDING"
    CONFIRMED_REVERSAL = "CONFIRMED_REVERSAL"
    SWEPT_NO_FOLLOWTHROUGH = "SWEPT_NO_FOLLOWTHROUGH"


@dataclass
class LiquiditySweep:
    """A single sweep event against a pool (wick-based)."""

    pool_id: int
    pool_type: PoolType
    direction: Direction  # direction of the sweep (BULLISH = swept a low, expecting reversal up)
    swept_index: int
    swept_price: float
    rejection: bool = False
    follow_through: SweepFollowThrough = SweepFollowThrough.PENDING
    resolving_structure_event_id: Optional[int] = None
    sweep_id: int = -1


@dataclass(frozen=True)
class DisplacementEvent:
    """A single-bar range-expansion event."""

    index: int
    direction: Direction
    range_: float
    atr: float


class MitigationState(str, Enum):
    OPEN = "OPEN"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
    FULLY_MITIGATED = "FULLY_MITIGATED"
    INVALIDATED = "OB_INVALIDATED"


class ZoneKind(str, Enum):
    FVG_BULLISH = "FVG_BULLISH"
    FVG_BEARISH = "FVG_BEARISH"
    ORDER_BLOCK_BULLISH = "ORDER_BLOCK_BULLISH"
    ORDER_BLOCK_BEARISH = "ORDER_BLOCK_BEARISH"
    BREAKER_BULLISH = "BREAKER_BULLISH"
    BREAKER_BEARISH = "BREAKER_BEARISH"


@dataclass
class Zone:
    """A price zone (FVG or Order Block) with a mitigation state machine."""

    kind: ZoneKind
    top: float
    bottom: float
    formed_index: int
    confirmed_index: int
    state: MitigationState = MitigationState.OPEN
    last_updated_index: Optional[int] = None
    reclassified_from: Optional[ZoneKind] = None
    zone_id: int = -1
    provisional: bool = False
    related_structure_event_id: Optional[int] = None


class RangeContext(str, Enum):
    PREMIUM = "PREMIUM"
    DISCOUNT = "DISCOUNT"
    EQUILIBRIUM = "EQUILIBRIUM"


@dataclass(frozen=True)
class DealingRangeContext:
    """Continuously recomputed premium/discount/equilibrium context."""

    index: int
    range_high: float
    range_low: float
    equilibrium: float
    context: RangeContext


@dataclass
class EngineResult:
    """Aggregate output of a full SMCEngine run over a bar series."""

    internal_swings: list = field(default_factory=list)
    external_swings: list = field(default_factory=list)
    structure_events: list = field(default_factory=list)
    liquidity_pools: list = field(default_factory=list)
    liquidity_sweeps: list = field(default_factory=list)
    displacement_events: list = field(default_factory=list)
    zones: list = field(default_factory=list)
    dealing_range_contexts: list = field(default_factory=list)
