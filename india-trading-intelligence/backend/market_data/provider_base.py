"""Abstract market data provider interface.

Any data source (a broker's REST/WebSocket API, a CSV replay file for
testing) implements this so `live/run_live_manual.py` and the SMC engine
never need to know which one is behind it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Callable, List

from .schema import NormalizedBar


class MarketDataProvider(ABC):
    @abstractmethod
    def get_historical_bars(
        self, symbol: str, exchange: str, interval: str, from_dt: datetime, to_dt: datetime
    ) -> List[NormalizedBar]:
        """Returns bars for a closed historical window. Must return an
        explicit empty list (never a fabricated bar) if the provider has
        no data for the requested range."""
        raise NotImplementedError

    @abstractmethod
    def get_ltp(self, symbol: str, exchange: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def subscribe_ticks(self, instruments: List[dict], on_tick: Callable[[dict], None]) -> None:
        """Starts a live tick subscription, invoking `on_tick` for every
        incoming tick. Blocking or non-blocking behavior is provider-
        specific - document it in the concrete implementation."""
        raise NotImplementedError
