"""Fixed-percentage risk position sizing and daily risk gate checks.

IMPORTANT: This module is implemented fully but is NEVER wired into any
order placement path in Release 1. Automation stays off by default —
nothing here places, modifies, or cancels an order. It exists so the
sizing/gating math is available for the Telegram alert text and for the
manual trader's own reference, and so later releases can wire it into
execution without redesigning it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 0.5       # % of account equity risked per trade
    max_daily_loss_pct: float = 2.0       # daily loss circuit breaker, % of starting-of-day equity
    max_trades_per_day: int = 5
    max_open_positions: int = 1

    def __post_init__(self) -> None:
        if not (0 < self.risk_per_trade_pct <= 100):
            raise ValueError("risk_per_trade_pct must be in (0, 100]")
        if not (0 < self.max_daily_loss_pct <= 100):
            raise ValueError("max_daily_loss_pct must be in (0, 100]")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be >= 1")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be >= 1")


@dataclass
class PositionSizeResult:
    quantity: int
    risk_amount: float
    risk_per_unit: float
    capped: bool = False
    note: str = ""


@dataclass
class DailyRiskState:
    """Mutable, per-trading-day state the gate checks against. The caller
    (live/run_live_manual.py in a later step) owns updating this as trades
    close and the day rolls over — this module never reads a clock or a
    broker itself."""

    trading_day: date
    starting_equity: float
    realized_pnl_today: float = 0.0
    trades_taken_today: int = 0
    open_positions: int = 0


@dataclass(frozen=True)
class RiskGateDecision:
    allowed: bool
    reasons: List[str] = field(default_factory=list)


class RiskEngine:
    def __init__(self, config: RiskConfig):
        self.config = config

    def position_size(
        self, account_equity: float, entry_price: float, stop_loss_price: float, lot_size: int = 1
    ) -> PositionSizeResult:
        """Fixed-% risk sizing: quantity such that (entry - stop) * quantity
        ~= risk_per_trade_pct% of account_equity, rounded down to whole
        lots. Returns quantity=0 (never a fabricated non-zero size) if the
        stop distance is zero/invalid or equity is non-positive."""

        risk_per_unit = abs(entry_price - stop_loss_price)
        if risk_per_unit <= 0 or account_equity <= 0 or lot_size <= 0:
            return PositionSizeResult(quantity=0, risk_amount=0.0, risk_per_unit=risk_per_unit, note="Invalid inputs — cannot size position.")

        risk_amount = account_equity * (self.config.risk_per_trade_pct / 100.0)
        raw_quantity = risk_amount / risk_per_unit
        lots = int(raw_quantity // lot_size)
        quantity = lots * lot_size
        capped = quantity == 0 and raw_quantity > 0

        note = "" if quantity > 0 else "Computed size rounds down to zero lots at this risk %."
        return PositionSizeResult(
            quantity=quantity, risk_amount=risk_amount, risk_per_unit=risk_per_unit, capped=capped, note=note
        )

    def check_daily_gate(self, state: DailyRiskState) -> RiskGateDecision:
        """Pure check — does NOT mutate state and does NOT touch any order
        path. Caller decides what to do with an `allowed=False` result
        (e.g. suppress further alerts for the day)."""

        reasons: List[str] = []

        if state.starting_equity > 0:
            loss_pct = -state.realized_pnl_today / state.starting_equity * 100.0
            if loss_pct >= self.config.max_daily_loss_pct:
                reasons.append(
                    f"Daily loss limit reached: {loss_pct:.2f}% >= {self.config.max_daily_loss_pct:.2f}%."
                )

        if state.trades_taken_today >= self.config.max_trades_per_day:
            reasons.append(
                f"Max trades per day reached: {state.trades_taken_today} >= {self.config.max_trades_per_day}."
            )

        if state.open_positions >= self.config.max_open_positions:
            reasons.append(
                f"Max open positions reached: {state.open_positions} >= {self.config.max_open_positions}."
            )

        return RiskGateDecision(allowed=len(reasons) == 0, reasons=reasons)
