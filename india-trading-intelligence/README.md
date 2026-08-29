# India Adaptive SMC Trading Intelligence Platform (Release 1)

A backend that monitors NIFTY/BANKNIFTY intraday structure using Smart
Money Concepts (SMC), and pushes Telegram alerts when structure/liquidity
events confirm a setup. **Manual execution only** — nothing in this
release places, modifies, or automates any order. See `BUILD_SPEC.md`
for the full spec this was built against.

## What's implemented (Release 1)

- `backend/smc/` — the full SMC detection engine: swings, structure
  (BOS/CHoCH/MSS), liquidity pools/sweeps, displacement, FVGs, order
  blocks (with breaker reclassification), and premium/discount context.
- `backend/signals/`, `backend/quant/`, `backend/risk/` — a signal state
  machine, trade-performance statistics, and fixed-% risk sizing/gating
  (implemented fully, never wired to any order path).
- `backend/notifications/` — a real Telegram Bot API integration
  (WhatsApp is a stub).
- `backend/brokers/angel_one.py` — a real Angel One SmartAPI integration
  (auth, historical data, LTP, WebSocket tick streaming). `place_order()`
  unconditionally refuses to run.
- `backend/market_data/`, `backend/ict/`, `backend/derivatives/`,
  `backend/cas/` — schemas and stubs for out-of-scope-for-now engines.
- `backtest/` — a synthetic data generator and a backtest runner that
  prints a full event log and saves an annotated candlestick chart.
- `live/run_live_manual.py` — wires market data → the SMC engine →
  signals → Telegram into one runnable pipeline, either replaying a CSV
  or polling Angel One live.
- `frontend/` — a Next.js dashboard (Dashboard, Signal Feed, Setup
  Detail, Journal, Settings) built against a mock data layer, ready to
  swap onto a real API later.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in the values you have
```

### Tests

```bash
python3 -m pytest
```

### Backtest (synthetic data, no credentials needed)

```bash
python3 -m backtest.run_backtest
```

Prints a full event log and saves `backtest/output_chart.png`.

## Telegram alerts

1. Create a bot via **@BotFather** on Telegram (`/newbot`), get the bot
   token.
2. Get your chat ID by messaging **@userinfobot**.
3. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, then confirm with:
   ```bash
   python3 -m scripts.send_test_telegram_message
   ```

## Angel One SmartAPI

1. Register an app at `smartapi.angelone.in` for `ANGEL_ONE_API_KEY`.
2. Enable TOTP at the "Enable TOTP" page for `ANGEL_ONE_TOTP_SECRET`
   (the base32 secret shown as an alternative to scanning the QR code).
3. `ANGEL_ONE_CLIENT_CODE` / `ANGEL_ONE_PASSWORD` are your existing Angel
   One login credentials.
4. Confirm the connection with:
   ```bash
   python3 -m scripts.test_angel_one_connection
   ```

A few response-body field names in `backend/brokers/angel_one.py` are
marked `TODO(verify)` — they weren't confirmed against a live response
or the docs site when this was built; check those before relying on
historical-candle or LTP data in anything important.

## Running the live pipeline

CSV replay (safe, no broker/network needed):

```bash
python3 -m live.run_live_manual --csv path/to/bars.csv --instrument NIFTY
```

CSV columns: `timestamp,open,high,low,close,volume`.

Live, against Angel One (requires the env vars above, plus the
instrument's numeric symbol token):

```bash
python3 -m live.run_live_manual --live --instrument NIFTY \
    --exchange NSE --symbol-token <token> --interval FIVE_MINUTE
```

This never places an order. It prints to the console and, if Telegram
is configured, sends the same alerts there.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs against a mock data layer (`frontend/src/lib/mock-data.ts`) — swap
`frontend/src/lib/data-source.ts`'s function bodies for real API calls
once one exists.

## Non-negotiable principles (see `BUILD_SPEC.md` for the full list)

- No repainting — nothing is detected before the bar that confirms it
  has closed.
- Never fabricate data — an unavailable source returns an explicit
  "unavailable" state, never a plausible-looking placeholder.
- Every threshold is configuration (`backend/smc/config.py`).
- BOS, CHoCH, and MSS are three distinct things, always.
- Structure events are close-based; liquidity sweeps are wick-based.
- A confluence score is a structured summary, never a probability.
- "No Trade" is a valid, normal output.
