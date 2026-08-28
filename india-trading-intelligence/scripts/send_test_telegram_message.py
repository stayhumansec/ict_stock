"""One-off script to confirm Telegram credentials actually work end-to-end.

Usage:
    export TELEGRAM_BOT_TOKEN="123456789:AA...your-token..."
    export TELEGRAM_CHAT_ID="123456789"
    python3 -m scripts.send_test_telegram_message
"""

from __future__ import annotations

import sys

from backend.notifications.base import Severity
from backend.notifications.telegram import TelegramNotifier


def main() -> int:
    notifier = TelegramNotifier()
    if not notifier.is_configured():
        print("TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID are not set in the environment.")
        return 1

    result = notifier.send(
        "This is a test message from the India Adaptive SMC Trading Intelligence Platform. "
        "If you can read this, Telegram alerts are wired up correctly.",
        Severity.INFO,
    )

    if result.success:
        print(f"Sent successfully at {result.sent_at.isoformat()}.")
        return 0

    print(f"Send FAILED: {result.error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
