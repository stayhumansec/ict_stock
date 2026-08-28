"""Basic trade-performance statistics: expectancy, profit factor, win rate,
drawdown, and a sample-size warning.

These operate on plain P&L numbers (one float per closed trade) so they
stay usable regardless of what eventually produces trades (backtest,
manual execution log, etc). Every function returns an explicit
"insufficient data" signal rather than a fabricated number when there
isn't enough input to compute something meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

MIN_SAMPLE_SIZE_FOR_CONFIDENCE = 30


@dataclass(frozen=True)
class StatsResult:
    value: Optional[float]
    sample_size: int
    sample_size_warning: Optional[str] = None


def sample_size_warning(n: int, min_n: int = MIN_SAMPLE_SIZE_FOR_CONFIDENCE) -> Optional[str]:
    if n == 0:
        return "No trades — statistic is undefined."
    if n < min_n:
        return f"Sample size ({n}) is below {min_n} — statistic is not yet reliable."
    return None


def win_rate(pnls: List[float]) -> StatsResult:
    n = len(pnls)
    if n == 0:
        return StatsResult(value=None, sample_size=0, sample_size_warning=sample_size_warning(0))
    wins = sum(1 for p in pnls if p > 0)
    return StatsResult(value=wins / n, sample_size=n, sample_size_warning=sample_size_warning(n))


def expectancy(pnls: List[float]) -> StatsResult:
    """Average P&L per trade."""
    n = len(pnls)
    if n == 0:
        return StatsResult(value=None, sample_size=0, sample_size_warning=sample_size_warning(0))
    return StatsResult(value=sum(pnls) / n, sample_size=n, sample_size_warning=sample_size_warning(n))


def profit_factor(pnls: List[float]) -> StatsResult:
    """gross profit / gross loss. None (not infinity) if there are no
    losing trades yet — never fabricate a finite number for an undefined
    ratio."""
    n = len(pnls)
    if n == 0:
        return StatsResult(value=None, sample_size=0, sample_size_warning=sample_size_warning(0))

    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)

    if gross_loss == 0:
        return StatsResult(value=None, sample_size=n, sample_size_warning="No losing trades yet — profit factor undefined.")

    return StatsResult(value=gross_profit / gross_loss, sample_size=n, sample_size_warning=sample_size_warning(n))


def max_drawdown(equity_curve: List[float]) -> StatsResult:
    """Largest peak-to-trough decline in the equity curve, expressed as a
    positive number (0 = no drawdown)."""
    n = len(equity_curve)
    if n == 0:
        return StatsResult(value=None, sample_size=0, sample_size_warning=sample_size_warning(0))

    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (peak - value) / peak
            max_dd = max(max_dd, drawdown)

    return StatsResult(value=max_dd, sample_size=n, sample_size_warning=sample_size_warning(n))
