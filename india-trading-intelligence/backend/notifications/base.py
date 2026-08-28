"""Notification channel interface.

Every channel (Telegram now, WhatsApp stubbed) implements the same shape
so `live/run_live_manual.py` never needs to know which channel it's
talking to. `is_configured()` must be checked before `send()` — a channel
that isn't configured (missing credentials, or a genuine stub) should
never be called and should never silently pretend to have sent something.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class Severity(str, Enum):
    INFO = "INFO"           # e.g. "No Trade" / context updates
    SETUP = "SETUP"         # a DEVELOPING/CONFIRMED signal worth watching
    ACTIONABLE = "ACTIONABLE"  # a TRIGGERED signal - manual execution decision point
    WARNING = "WARNING"     # risk gate blocked, data unavailable, etc.
    CRITICAL = "CRITICAL"   # engine/connectivity failure


@dataclass(frozen=True)
class NotificationResult:
    success: bool
    sent_at: datetime
    error: str = ""


class NotificationChannel(ABC):
    @abstractmethod
    def is_configured(self) -> bool:
        """True only if this channel has everything it needs to actually
        send (credentials present, etc). Never returns True speculatively."""
        raise NotImplementedError

    @abstractmethod
    def send(self, message: str, severity: Severity) -> NotificationResult:
        raise NotImplementedError

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
