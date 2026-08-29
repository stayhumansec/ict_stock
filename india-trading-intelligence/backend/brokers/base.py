"""Abstract broker interface.

A broker is a MarketDataProvider (historical bars, LTP, live ticks) that
additionally supports authentication and order placement. `place_order`
is part of the interface because a future release will need it, but
every concrete Release 1 implementation must refuse to actually execute
it - see `angel_one.py`.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Optional

from backend.market_data.provider_base import MarketDataProvider


@dataclass(frozen=True)
class OrderRequest:
    """Shape only - see place_order() docstrings for why this is never
    actually submitted in Release 1."""

    trading_symbol: str
    symbol_token: str
    exchange: str
    transaction_type: str  # "BUY" | "SELL"
    order_type: str  # "MARKET" | "LIMIT" | ...
    product_type: str
    quantity: int
    price: Optional[float] = None


class BrokerInterface(MarketDataProvider):
    @abstractmethod
    def authenticate(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def logout(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, order: OrderRequest) -> str:
        """Must raise in every Release 1 broker implementation.
        Automation stays off by default - no order path may ever reach a
        real broker in this release."""
        raise NotImplementedError
