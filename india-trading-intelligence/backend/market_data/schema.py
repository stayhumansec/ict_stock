"""Normalized market data shapes shared across providers.

`NormalizedBar` intentionally carries derivatives-shaped fields (oi,
expiry, strike, option_type) even though nothing in Release 1 populates
them — derivatives are out of scope for this release, but the schema
needs to already accommodate them so wiring the derivatives engine in
later doesn't require reshaping every provider that has been built by
then.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

OptionType = Literal["CE", "PE"]


@dataclass(frozen=True)
class NormalizedBar:
    symbol: str
    exchange: str
    interval: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    # Derivatives-shaped fields - always None in Release 1 (no options/
    # futures data source is wired up). Never populate these with a
    # fabricated value; leave them None until a real derivatives provider
    # exists.
    oi: Optional[float] = None
    expiry: Optional[str] = None
    strike: Optional[float] = None
    option_type: Optional[OptionType] = None
