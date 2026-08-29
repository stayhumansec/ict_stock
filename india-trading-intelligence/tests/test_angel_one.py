import struct
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from backend.brokers import angel_one
from backend.brokers.angel_one import (
    AngelOneAPIError,
    AngelOneAuthError,
    AngelOneBroker,
    AngelOneConfig,
    _AngelOneWebSocket,
)
from backend.brokers.base import OrderRequest


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    # Never let a test hit the real network for the public-IP lookup.
    monkeypatch.setattr(angel_one, "_best_effort_public_ip", lambda: "1.2.3.4")


def make_config(**overrides):
    defaults = dict(api_key="key", client_code="C1", password="pw", totp_secret="JBSWY3DPEHPK3PXP")
    defaults.update(overrides)
    return AngelOneConfig(**defaults)


def fake_response(json_body, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.text = str(json_body)
    return resp


def test_config_from_env_missing_vars_raises(monkeypatch):
    monkeypatch.delenv("ANGEL_ONE_API_KEY", raising=False)
    monkeypatch.delenv("ANGEL_ONE_CLIENT_CODE", raising=False)
    monkeypatch.delenv("ANGEL_ONE_PASSWORD", raising=False)
    monkeypatch.delenv("ANGEL_ONE_TOTP_SECRET", raising=False)
    with pytest.raises(AngelOneAuthError):
        AngelOneConfig.from_env()


def test_config_from_env_success(monkeypatch):
    monkeypatch.setenv("ANGEL_ONE_API_KEY", "k")
    monkeypatch.setenv("ANGEL_ONE_CLIENT_CODE", "c")
    monkeypatch.setenv("ANGEL_ONE_PASSWORD", "p")
    monkeypatch.setenv("ANGEL_ONE_TOTP_SECRET", "JBSWY3DPEHPK3PXP")
    config = AngelOneConfig.from_env()
    assert config.api_key == "k"


def test_authenticate_success_stores_tokens():
    broker = AngelOneBroker(make_config())
    login_response = fake_response(
        {"status": True, "data": {"jwtToken": "jwt123", "refreshToken": "refresh123", "feedToken": "feed123"}}
    )
    with patch("backend.brokers.angel_one.requests.request", return_value=login_response) as mock_req:
        result = broker.authenticate()

    assert result is True
    assert broker._jwt_token == "jwt123"
    assert broker._refresh_token == "refresh123"
    assert broker._feed_token == "feed123"
    call = mock_req.call_args
    assert call.args[0] == "POST"
    assert call.args[1].endswith("/rest/auth/angelbroking/user/v1/loginByPassword")


def test_authenticate_failure_raises():
    broker = AngelOneBroker(make_config())
    login_response = fake_response({"status": False, "message": "Invalid TOTP"})
    with patch("backend.brokers.angel_one.requests.request", return_value=login_response):
        with pytest.raises(AngelOneAuthError, match="Invalid TOTP"):
            broker.authenticate()
    assert broker._jwt_token is None


def test_headers_require_auth_without_token_raises():
    broker = AngelOneBroker(make_config())
    with pytest.raises(AngelOneAuthError):
        broker._headers(requires_auth=True)


def test_headers_include_all_documented_fields():
    broker = AngelOneBroker(make_config())
    broker._jwt_token = "jwt123"
    headers = broker._headers(requires_auth=True)
    for key in (
        "Content-Type",
        "Accept",
        "X-UserType",
        "X-SourceID",
        "X-ClientLocalIP",
        "X-ClientPublicIP",
        "X-MACAddress",
        "X-PrivateKey",
        "Authorization",
    ):
        assert key in headers
    assert headers["Authorization"] == "Bearer jwt123"
    assert headers["X-PrivateKey"] == "key"


def test_get_historical_bars_parses_candles():
    broker = AngelOneBroker(make_config())
    broker._jwt_token = "jwt123"
    candle_response = fake_response(
        {
            "status": True,
            "data": [
                ["2024-01-01T09:15:00+05:30", 100.0, 105.0, 99.0, 104.0, 12345],
                ["2024-01-01T09:20:00+05:30", 104.0, 106.0, 103.0, 105.5, 6789],
            ],
        }
    )
    with patch("backend.brokers.angel_one.requests.request", return_value=candle_response):
        bars = broker.get_historical_bars(
            "3045", "NSE", "FIVE_MINUTE", datetime(2024, 1, 1, 9, 0), datetime(2024, 1, 1, 10, 0)
        )

    assert len(bars) == 2
    assert bars[0].open == 100.0
    assert bars[0].close == 104.0
    assert bars[0].volume == 12345
    assert bars[0].symbol == "3045"
    assert bars[0].exchange == "NSE"


def test_get_historical_bars_failure_raises():
    broker = AngelOneBroker(make_config())
    broker._jwt_token = "jwt123"
    with patch(
        "backend.brokers.angel_one.requests.request",
        return_value=fake_response({"status": False, "message": "bad token"}),
    ):
        with pytest.raises(AngelOneAPIError):
            broker.get_historical_bars("bad", "NSE", "FIVE_MINUTE", datetime.now(), datetime.now())


def test_get_ltp_resolves_token_then_fetches_price():
    broker = AngelOneBroker(make_config())
    broker._jwt_token = "jwt123"

    search_response = fake_response(
        {"status": True, "data": [{"exchange": "NSE", "tradingsymbol": "SBIN-EQ", "symboltoken": "3045"}]}
    )
    ltp_response = fake_response({"status": True, "data": {"ltp": 601.5}})

    with patch("backend.brokers.angel_one.requests.request", side_effect=[search_response, ltp_response]) as mock_req:
        price = broker.get_ltp("SBIN-EQ", "NSE")

    assert price == 601.5
    assert broker._symbol_token_cache[("NSE", "SBIN-EQ")] == "3045"
    assert mock_req.call_count == 2


def test_get_ltp_uses_cache_on_second_call():
    broker = AngelOneBroker(make_config())
    broker._jwt_token = "jwt123"
    broker._symbol_token_cache[("NSE", "SBIN-EQ")] = "3045"

    ltp_response = fake_response({"status": True, "data": {"ltp": 602.0}})
    with patch("backend.brokers.angel_one.requests.request", return_value=ltp_response) as mock_req:
        price = broker.get_ltp("SBIN-EQ", "NSE")

    assert price == 602.0
    assert mock_req.call_count == 1  # no searchScrip call needed


def test_place_order_always_refused():
    broker = AngelOneBroker(make_config())
    broker._jwt_token = "jwt123"  # even if authenticated
    order = OrderRequest(
        trading_symbol="SBIN-EQ",
        symbol_token="3045",
        exchange="NSE",
        transaction_type="BUY",
        order_type="MARKET",
        product_type="INTRADAY",
        quantity=1,
    )
    with pytest.raises(RuntimeError, match="refused"):
        broker.place_order(order)


def test_logout_clears_tokens():
    broker = AngelOneBroker(make_config())
    broker._jwt_token = "jwt123"
    broker._refresh_token = "r"
    broker._feed_token = "f"
    with patch("backend.brokers.angel_one.requests.request", return_value=fake_response({"status": True})):
        broker.logout()
    assert broker._jwt_token is None
    assert broker._refresh_token is None
    assert broker._feed_token is None


def test_logout_noop_when_not_authenticated():
    broker = AngelOneBroker(make_config())
    with patch("backend.brokers.angel_one.requests.request") as mock_req:
        broker.logout()
    mock_req.assert_not_called()


def _build_ltp_tick_frame(token: str, ltp_paise_or_rupee: int) -> bytes:
    """Builds a synthetic binary tick frame matching the documented
    LTP_MODE layout: [mode:1][exchange_type:1][token:25][seq:8][ts:8][ltp:8]."""
    token_bytes = token.encode().ljust(25, b"\x00")
    return (
        struct.pack("<B", 1)  # subscription_mode = LTP
        + struct.pack("<B", 1)  # exchange_type = NSE_CM
        + token_bytes
        + struct.pack("<q", 42)  # sequence_number
        + struct.pack("<q", 1700000000)  # exchange_timestamp
        + struct.pack("<q", ltp_paise_or_rupee)  # last_traded_price
    )


def test_websocket_parses_ltp_tick_frame():
    ws = _AngelOneWebSocket(
        auth_token="jwt", api_key="key", client_code="C1", feed_token="feed", instruments=[], on_tick=lambda t: None
    )
    frame = _build_ltp_tick_frame("26009", 220050)
    tick = ws._parse_binary_tick(frame)

    assert tick["subscription_mode"] == 1
    assert tick["exchange_type"] == 1
    assert tick["token"] == "26009"
    assert tick["sequence_number"] == 42
    assert tick["last_traded_price"] == 220050  # NOT divided by 100 - see note in source


def test_websocket_ignores_short_frames():
    ws = _AngelOneWebSocket(
        auth_token="jwt", api_key="key", client_code="C1", feed_token="feed", instruments=[], on_tick=lambda t: None
    )
    assert ws._parse_binary_tick(b"\x00\x01") is None
