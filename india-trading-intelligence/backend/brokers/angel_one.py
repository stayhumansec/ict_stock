"""Angel One SmartAPI broker integration.

This is a REAL implementation against Angel One's SmartAPI, not a stub -
but several response-body field names below are marked with TODO because
they could not be confirmed against the live docs site
(https://smartapi.angelone.in/docs was unreachable from this environment
at the time of writing) or against the official SDK, which itself only
passes those response bodies through unparsed. Everything else (base
URL, route paths, request headers, request parameter shapes, the
WebSocket URL, subscribe payload shape, and the binary tick format) is
taken directly from Angel One's own official Python SDK source
(https://github.com/angel-one/smartapi-python, SmartApi/smartConnect.py
and SmartApi/smartWebSocketV2.py, fetched and read directly rather than
guessed) and from the official Go SDK
(https://github.com/angel-one/smartapigo) as a cross-check.

Do not remove a TODO below by guessing what the field name "probably" is
- verify it against a real API response first.
"""

from __future__ import annotations

import json
import os
import struct
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

import requests

from backend.brokers.base import BrokerInterface, OrderRequest
from backend.market_data.schema import NormalizedBar

ROOT_URL = "https://apiconnect.angelone.in"
WEBSOCKET_URL = "wss://smartapisocket.angelone.in/smart-stream"

# Copied verbatim from SmartApi/smartConnect.py's `_routes` dict (official
# SDK). Only the routes this module actually uses are included; the rest
# were left out rather than copied speculatively.
ROUTES = {
    "api.login": "/rest/auth/angelbroking/user/v1/loginByPassword",
    "api.logout": "/rest/secure/angelbroking/user/v1/logout",
    "api.token": "/rest/auth/angelbroking/jwt/v1/generateTokens",
    "api.user.profile": "/rest/secure/angelbroking/user/v1/getProfile",
    "api.ltp.data": "/rest/secure/angelbroking/order/v1/getLtpData",
    "api.candle.data": "/rest/secure/angelbroking/historical/v1/getCandleData",
    "api.order.place": "/rest/secure/angelbroking/order/v1/placeOrder",
    "api.search.scrip": "/rest/secure/angelbroking/order/v1/searchScrip",
}

# Subscription modes and exchange type codes, from SmartWebSocketV2's
# class constants and its subscribe() docstring (official SDK).
LTP_MODE = 1
QUOTE_MODE = 2
SNAP_QUOTE_MODE = 3
DEPTH_MODE = 4

EXCHANGE_TYPE = {
    "NSE_CM": 1,
    "NSE_FO": 2,
    "BSE_CM": 3,
    "BSE_FO": 4,
    "MCX_FO": 5,
    "NCX_FO": 7,
    "CDE_FO": 13,
}


class AngelOneAuthError(RuntimeError):
    pass


class AngelOneAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class AngelOneConfig:
    api_key: str
    client_code: str
    password: str
    totp_secret: str

    @classmethod
    def from_env(cls) -> "AngelOneConfig":
        api_key = os.environ.get("ANGEL_ONE_API_KEY")
        client_code = os.environ.get("ANGEL_ONE_CLIENT_CODE")
        password = os.environ.get("ANGEL_ONE_PASSWORD")
        totp_secret = os.environ.get("ANGEL_ONE_TOTP_SECRET")

        missing = [
            name
            for name, value in (
                ("ANGEL_ONE_API_KEY", api_key),
                ("ANGEL_ONE_CLIENT_CODE", client_code),
                ("ANGEL_ONE_PASSWORD", password),
                ("ANGEL_ONE_TOTP_SECRET", totp_secret),
            )
            if not value
        ]
        if missing:
            raise AngelOneAuthError(f"Missing required environment variables: {', '.join(missing)}")

        return cls(api_key=api_key, client_code=client_code, password=password, totp_secret=totp_secret)


def _generate_totp(secret: str) -> str:
    import pyotp

    return pyotp.TOTP(secret).now()


def _best_effort_public_ip() -> str:
    # Angel One's own SDK does the same best-effort lookup with the same
    # hardcoded fallback (see smartConnect.py) - these header values
    # appear to be informational/logging on Angel One's side rather than
    # strictly validated, but that is not confirmed from documentation.
    try:
        return requests.get("https://api.ipify.org", timeout=3).text.strip()
    except Exception:
        return "106.193.147.98"


def _local_ip() -> str:
    import socket

    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def _mac_address() -> str:
    hex_digits = "%012x" % uuid.getnode()
    return ":".join(hex_digits[i : i + 2] for i in range(0, 12, 2))


class AngelOneBroker(BrokerInterface):
    def __init__(self, config: Optional[AngelOneConfig] = None):
        self.config = config or AngelOneConfig.from_env()
        self._jwt_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._feed_token: Optional[str] = None
        self._client_public_ip = _best_effort_public_ip()
        self._client_local_ip = _local_ip()
        self._client_mac = _mac_address()
        self._symbol_token_cache: dict = {}

    # --- Authentication -----------------------------------------------

    def authenticate(self) -> bool:
        totp = _generate_totp(self.config.totp_secret)
        payload = {
            "clientcode": self.config.client_code,
            "password": self.config.password,
            "totp": totp,
        }
        response = self._request("api.login", "POST", payload, requires_auth=False)

        if not response.get("status"):
            raise AngelOneAuthError(f"Angel One login failed: {response.get('message', response)}")

        data = response["data"]
        self._jwt_token = data["jwtToken"]
        self._refresh_token = data["refreshToken"]
        self._feed_token = data["feedToken"]
        return True

    def logout(self) -> None:
        if self._jwt_token is None:
            return
        self._request("api.logout", "POST", {"clientcode": self.config.client_code})
        self._jwt_token = None
        self._refresh_token = None
        self._feed_token = None

    def _require_authenticated(self) -> None:
        if self._jwt_token is None:
            raise AngelOneAuthError("Not authenticated - call authenticate() first.")

    # --- Internal request plumbing --------------------------------------

    def _headers(self, requires_auth: bool) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": self._client_local_ip,
            "X-ClientPublicIP": self._client_public_ip,
            "X-MACAddress": self._client_mac,
            "X-PrivateKey": self.config.api_key,
        }
        if requires_auth:
            self._require_authenticated()
            headers["Authorization"] = f"Bearer {self._jwt_token}"
        return headers

    def _request(self, route_key: str, method: str, params: dict, requires_auth: bool = True) -> dict:
        url = ROOT_URL + ROUTES[route_key]
        headers = self._headers(requires_auth)

        try:
            response = requests.request(
                method,
                url,
                data=json.dumps(params) if method in ("POST", "PUT") else None,
                params=params if method in ("GET", "DELETE") else None,
                headers=headers,
                timeout=10,
            )
        except requests.RequestException as exc:
            raise AngelOneAPIError(f"Request to {route_key} failed: {exc}") from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise AngelOneAPIError(
                f"Non-JSON response from {route_key}: HTTP {response.status_code}: {response.text[:500]}"
            ) from exc

        if response.status_code >= 400 and not body.get("status"):
            raise AngelOneAPIError(f"{route_key} returned HTTP {response.status_code}: {body}")

        return body

    # --- Market data (MarketDataProvider) -------------------------------

    def get_historical_bars(
        self, symbol: str, exchange: str, interval: str, from_dt: datetime, to_dt: datetime
    ) -> List[NormalizedBar]:
        """`symbol` here must be Angel One's numeric `symboltoken`, not the
        trading symbol string - the historical endpoint keys off token,
        per the official SDK's example (README.md: symboltoken="3045").
        """
        params = {
            "exchange": exchange,
            "symboltoken": symbol,
            "interval": interval,
            "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
            "todate": to_dt.strftime("%Y-%m-%d %H:%M"),
        }
        response = self._request("api.candle.data", "POST", params)

        if not response.get("status"):
            raise AngelOneAPIError(f"getCandleData failed: {response.get('message', response)}")

        bars: List[NormalizedBar] = []
        # TODO(verify): each candle's array shape is assumed to be
        # [timestamp_iso8601, open, high, low, close, volume], which is
        # Angel One's commonly documented historical-candle format, but
        # this was NOT confirmed against a live response or the current
        # docs site (blocked from this environment) - verify against a
        # real getCandleData response before relying on this in
        # production, and fix here if the field order differs.
        for candle in response.get("data", []) or []:
            ts_raw, o, h, l, c, v = candle
            bars.append(
                NormalizedBar(
                    symbol=symbol,
                    exchange=exchange,
                    interval=interval,
                    timestamp=datetime.fromisoformat(ts_raw),
                    open=float(o),
                    high=float(h),
                    low=float(l),
                    close=float(c),
                    volume=float(v),
                )
            )
        return bars

    def get_ltp(self, symbol: str, exchange: str) -> float:
        """`symbol` is the Angel One trading symbol string (e.g.
        "SBIN-EQ"), matching ltpData()'s `tradingsymbol` param in the
        official SDK. The LTP endpoint also requires a numeric
        symbol_token, which is resolved (and cached) via searchScrip - a
        real, documented endpoint in the same SDK, not a fabricated
        lookup."""
        symbol_token = self._resolve_symbol_token(exchange, symbol)
        return self.get_ltp_by_token(exchange, symbol, symbol_token)

    def _resolve_symbol_token(self, exchange: str, trading_symbol: str) -> str:
        cache_key = (exchange, trading_symbol)
        if cache_key in self._symbol_token_cache:
            return self._symbol_token_cache[cache_key]

        response = self._request(
            "api.search.scrip", "POST", {"exchange": exchange, "searchscrip": trading_symbol}
        )
        if not response.get("status") or not response.get("data"):
            raise AngelOneAPIError(f"searchScrip found no match for {exchange}:{trading_symbol}: {response}")

        # TODO(verify): assumes the first exact tradingsymbol match is the
        # right one when searchScrip returns multiple results (it can, for
        # partial matches) - not confirmed against a live response with
        # multiple hits.
        for item in response["data"]:
            if item.get("tradingsymbol") == trading_symbol:
                token = item["symboltoken"]
                self._symbol_token_cache[cache_key] = token
                return token

        raise AngelOneAPIError(f"searchScrip returned results but none matched {trading_symbol} exactly")

    def get_ltp_by_token(self, exchange: str, trading_symbol: str, symbol_token: str) -> float:
        params = {"exchange": exchange, "tradingsymbol": trading_symbol, "symboltoken": symbol_token}
        response = self._request("api.ltp.data", "POST", params)

        if not response.get("status"):
            raise AngelOneAPIError(f"getLtpData failed: {response.get('message', response)}")

        # TODO(verify): the official SDK returns this response unparsed,
        # so the exact key holding the price inside `data` (assumed here
        # to be "ltp") was not confirmed against a live response or the
        # docs site. Verify before trusting this value.
        return float(response["data"]["ltp"])

    def subscribe_ticks(self, instruments: List[dict], on_tick: Callable[[dict], None]) -> None:
        """Starts a blocking WebSocket connection (SmartAPI WebSocket V2)
        and calls `on_tick` for every parsed tick. `instruments` must be
        shaped like the official SDK's `token_list`:
        [{"exchangeType": 1, "tokens": ["26009"]}, ...] - see
        EXCHANGE_TYPE above for the exchangeType codes.

        Runs forever until the connection closes or the process is
        killed - callers wanting non-blocking behavior should run this in
        its own thread (see start_tick_stream_in_background below).
        """
        self._require_authenticated()
        _AngelOneWebSocket(
            auth_token=self._jwt_token,
            api_key=self.config.api_key,
            client_code=self.config.client_code,
            feed_token=self._feed_token,
            instruments=instruments,
            on_tick=on_tick,
        ).run_forever()

    def start_tick_stream_in_background(self, instruments: List[dict], on_tick: Callable[[dict], None]) -> threading.Thread:
        thread = threading.Thread(target=self.subscribe_ticks, args=(instruments, on_tick), daemon=True)
        thread.start()
        return thread

    # --- Order placement -------------------------------------------------

    def place_order(self, order: OrderRequest) -> str:
        raise RuntimeError(
            "place_order() is refused in Release 1. Automation stays off by default - no order path may "
            "reach Angel One in this release. This method exists only so the BrokerInterface shape is "
            "complete for a later release; it must never be called from any signal or live-run path."
        )


class _AngelOneWebSocket:
    """SmartAPI WebSocket V2 client.

    The connection URL, required headers, subscribe payload shape, and
    binary tick-frame layout below are ported directly from Angel One's
    official SDK (SmartApi/smartWebSocketV2.py) - not guessed. Only
    LTP_MODE and QUOTE_MODE/SNAP_QUOTE_MODE parsing is implemented;
    DEPTH_MODE's 20-level order book frame layout was not ported since
    nothing in this release needs order-book depth.
    """

    HEARTBEAT_INTERVAL_SEC = 10

    def __init__(
        self,
        auth_token: str,
        api_key: str,
        client_code: str,
        feed_token: str,
        instruments: List[dict],
        on_tick: Callable[[dict], None],
    ):
        self.auth_token = auth_token
        self.api_key = api_key
        self.client_code = client_code
        self.feed_token = feed_token
        self.instruments = instruments
        self.on_tick = on_tick
        self._ws = None

    def run_forever(self) -> None:
        import websocket  # websocket-client package

        headers = [
            f"Authorization: {self.auth_token}",
            f"x-api-key: {self.api_key}",
            f"x-client-code: {self.client_code}",
            f"x-feed-token: {self.feed_token}",
        ]

        def _on_open(ws):
            request = {
                "correlationID": "smc-engine",
                "action": 1,  # SUBSCRIBE_ACTION
                "params": {"mode": LTP_MODE, "tokenList": self.instruments},
            }
            ws.send(json.dumps(request))

        def _on_message(ws, message):
            if isinstance(message, (bytes, bytearray)):
                tick = self._parse_binary_tick(message)
                if tick is not None:
                    self.on_tick(tick)

        def _on_ping(ws, data):
            ws.send("pong")

        self._ws = websocket.WebSocketApp(
            WEBSOCKET_URL,
            header=headers,
            on_open=_on_open,
            on_message=_on_message,
            on_ping=_on_ping,
        )
        self._ws.run_forever(ping_interval=self.HEARTBEAT_INTERVAL_SEC)

    def stop(self) -> None:
        if self._ws is not None:
            self._ws.close()

    @staticmethod
    def _unpack(data: bytes, start: int, end: int, fmt: str):
        return struct.unpack("<" + fmt, data[start:end])

    @staticmethod
    def _parse_token(chunk: bytes) -> str:
        token = ""
        for b in chunk:
            if b == 0:
                break
            token += chr(b)
        return token

    def _parse_binary_tick(self, data: bytes) -> Optional[dict]:
        if len(data) < 51:
            return None

        # NOTE: field byte offsets and the "q" (int64) formats below are
        # copied exactly from SmartWebSocketV2._parse_binary_data() in the
        # official SDK. That method does NOT divide any of these integers
        # by 100 before returning them, so neither do we here - do not
        # add paise-to-rupee scaling without confirming it against a real
        # tick first. If prices come out looking 100x too large, that's
        # the thing to check.
        subscription_mode = self._unpack(data, 0, 1, "B")[0]
        tick = {
            "subscription_mode": subscription_mode,
            "exchange_type": self._unpack(data, 1, 2, "B")[0],
            "token": self._parse_token(data[2:27]),
            "sequence_number": self._unpack(data, 27, 35, "q")[0],
            "exchange_timestamp": self._unpack(data, 35, 43, "q")[0],
            "last_traded_price": self._unpack(data, 43, 51, "q")[0],
        }

        if subscription_mode in (QUOTE_MODE, SNAP_QUOTE_MODE) and len(data) >= 123:
            tick["last_traded_quantity"] = self._unpack(data, 51, 59, "q")[0]
            tick["average_traded_price"] = self._unpack(data, 59, 67, "q")[0]
            tick["volume_trade_for_the_day"] = self._unpack(data, 67, 75, "q")[0]
            tick["open_price_of_the_day"] = self._unpack(data, 91, 99, "q")[0]
            tick["high_price_of_the_day"] = self._unpack(data, 99, 107, "q")[0]
            tick["low_price_of_the_day"] = self._unpack(data, 107, 115, "q")[0]
            tick["closed_price"] = self._unpack(data, 115, 123, "q")[0]

        return tick
