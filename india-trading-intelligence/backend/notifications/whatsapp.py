"""WhatsApp notification channel — STUB ONLY for Release 1.

WhatsApp integration is explicitly out of scope (see BUILD_SPEC.md).
`is_configured()` always returns False, and `send()` raises
NotImplementedError rather than pretending to deliver a message — the
same "never fabricate" contract used by the derivatives/ and cas/ stubs.
"""

from __future__ import annotations

from .base import NotificationChannel, NotificationResult, Severity


class WhatsAppNotifier(NotificationChannel):
    def is_configured(self) -> bool:
        return False

    def send(self, message: str, severity: Severity) -> NotificationResult:
        raise NotImplementedError("WhatsApp integration is not implemented in Release 1 (DATA_UNAVAILABLE).")
