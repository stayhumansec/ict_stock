import pytest

from backend.notifications.base import Severity
from backend.notifications.telegram import TelegramNotifier
from backend.notifications.whatsapp import WhatsAppNotifier


class FakeResponse:
    def __init__(self, status_code=200, json_body=None, text=""):
        self.status_code = status_code
        self._json_body = json_body if json_body is not None else {"ok": True}
        self.text = text

    def json(self):
        return self._json_body


def test_telegram_not_configured_without_credentials():
    notifier = TelegramNotifier(bot_token=None, chat_id=None)
    assert notifier.is_configured() is False
    result = notifier.send("hello", Severity.INFO)
    assert result.success is False
    assert "not configured" in result.error.lower()


def test_telegram_configured_with_explicit_credentials():
    notifier = TelegramNotifier(bot_token="123:ABC", chat_id="999")
    assert notifier.is_configured() is True


def test_telegram_send_success_mocked_http():
    notifier = TelegramNotifier(bot_token="123:ABC", chat_id="999")
    captured = {}

    def fake_post(url, payload):
        captured["url"] = url
        captured["payload"] = payload
        return FakeResponse(status_code=200, json_body={"ok": True})

    notifier._post = fake_post
    result = notifier.send("Test alert", Severity.SETUP)
    assert result.success is True
    assert "123:ABC" in captured["url"]
    assert captured["payload"]["chat_id"] == "999"
    assert "[SETUP]" in captured["payload"]["text"]
    assert "Test alert" in captured["payload"]["text"]


def test_telegram_send_handles_http_error_status():
    notifier = TelegramNotifier(bot_token="123:ABC", chat_id="999")
    notifier._post = lambda url, payload: FakeResponse(status_code=401, text="Unauthorized")
    result = notifier.send("hello", Severity.INFO)
    assert result.success is False
    assert "401" in result.error


def test_telegram_send_handles_api_ok_false():
    notifier = TelegramNotifier(bot_token="123:ABC", chat_id="999")
    notifier._post = lambda url, payload: FakeResponse(status_code=200, json_body={"ok": False, "description": "bad chat id"})
    result = notifier.send("hello", Severity.INFO)
    assert result.success is False
    assert "ok=false" in result.error.lower()


def test_telegram_send_handles_network_exception():
    notifier = TelegramNotifier(bot_token="123:ABC", chat_id="999")

    def raise_error(url, payload):
        raise ConnectionError("DNS failure")

    notifier._post = raise_error
    result = notifier.send("hello", Severity.INFO)
    assert result.success is False
    assert "DNS failure" in result.error


def test_whatsapp_is_never_configured():
    notifier = WhatsAppNotifier()
    assert notifier.is_configured() is False


def test_whatsapp_send_raises_not_implemented():
    notifier = WhatsAppNotifier()
    with pytest.raises(NotImplementedError):
        notifier.send("hello", Severity.INFO)
