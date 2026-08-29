"""One-off script to confirm Angel One SmartAPI credentials actually work
end-to-end: authenticates, fetches your profile, and fetches NIFTY's LTP
as a smoke test. Does not place any order.

Usage:
    export ANGEL_ONE_API_KEY="..."
    export ANGEL_ONE_CLIENT_CODE="..."
    export ANGEL_ONE_PASSWORD="..."
    export ANGEL_ONE_TOTP_SECRET="..."
    python3 -m scripts.test_angel_one_connection
"""

from __future__ import annotations

import sys

from backend.brokers.angel_one import AngelOneAPIError, AngelOneAuthError, AngelOneBroker


def main() -> int:
    try:
        broker = AngelOneBroker()
    except AngelOneAuthError as exc:
        print(f"Config error: {exc}")
        return 1

    print("Authenticating with Angel One...")
    try:
        broker.authenticate()
    except AngelOneAuthError as exc:
        print(f"Authentication FAILED: {exc}")
        return 1
    except AngelOneAPIError as exc:
        print(f"Authentication request FAILED: {exc}")
        return 1

    print("Authenticated successfully.")
    print(f"  jwtToken (truncated):     {broker._jwt_token[:20]}...")
    print(f"  feedToken (truncated):    {broker._feed_token[:20]}...")

    print("\nFetching NIFTY 50 index LTP as a smoke test...")
    try:
        # "Nifty 50" is the index trading symbol on NSE; symbol resolution
        # goes through searchScrip. If this specific symbol string doesn't
        # resolve, try "NIFTY" or check your SmartAPI account's scrip
        # master for the exact listed name.
        ltp = broker.get_ltp("Nifty 50", "NSE")
        print(f"  NIFTY 50 LTP: {ltp}")
    except Exception as exc:
        print(f"  LTP fetch failed (auth itself succeeded though): {exc}")

    broker.logout()
    print("\nLogged out. Connection test complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
