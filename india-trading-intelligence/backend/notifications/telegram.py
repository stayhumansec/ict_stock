"""Real Telegram Bot API integration.

Reads TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID from the environment by
default (can be overridden for tests / explicit construction). Uses the
plain `sendMessage` Bot API call — https://core.telegram.org/bots/api.

This is the actual end of the alert pipeline for Release 1: nothing here
places or modifies any order.
"""

from __future__ import annotations

import os
from typing import Optional

from .base import NotificationChannel, NotificationResult, Severity

TELEGRAM_API_BASE = "https://api.telegram.org"

_SEVERITY_TAG = {
    Severity.INFO: "[INFO]",
    Severity.SETUP: "[SETUP]",
    Severity.ACTIONABLE: "[ACTIONABLE]",
    Severity.WARNING: "[WARNING]",
    Severity.CRITICAL: "[CRITICAL]",
}


class TelegramNotifier(NotificationChannel):
    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ):
        self.bot_token = bot_token if bot_token is not None else os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id if chat_id is not None else os.environ.get("TELEGRAM_CHAT_ID")
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.bot_token) and bool(self.chat_id)

    def send(self, message: str, severity: Severity) -> NotificationResult:
        if not self.is_configured():
            return NotificationResult(
                success=False,
                sent_at=self._now(),
                error="Telegram not configured — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
            )

        tag = _SEVERITY_TAG.get(severity, "")
        text = f"{tag} {message}" if tag else message
        url = f"{TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text}

        try:
            response = self._post(url, payload)
        except Exception as exc:  # network failure, DNS, timeout, etc.
            return NotificationResult(success=False, sent_at=self._now(), error=f"Telegram request failed: {exc}")

        if response.status_code != 200:
            return NotificationResult(
                success=False,
                sent_at=self._now(),
                error=f"Telegram API returned HTTP {response.status_code}: {response.text}",
            )

        body = response.json()
        if not body.get("ok", False):
            return NotificationResult(success=False, sent_at=self._now(), error=f"Telegram API returned ok=false: {body}")

        return NotificationResult(success=True, sent_at=self._now())

    def _post(self, url: str, payload: dict):
        """Isolated so tests can monkeypatch this single method instead of
        mocking the network stack."""
        import requests

        return requests.post(url, json=payload, timeout=self.timeout_seconds)
