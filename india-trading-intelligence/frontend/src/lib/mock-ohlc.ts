import type { UTCTimestamp } from "lightweight-charts";

export interface OhlcBar {
  time: UTCTimestamp;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** Deterministic PRNG (mulberry32) so the same signal always renders the
 * same illustrative candles instead of reshuffling on every render. */
function mulberry32(seed: number) {
  let a = seed;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashSeed(input: string): number {
  let h = 0;
  for (let i = 0; i < input.length; i++) {
    h = (Math.imul(31, h) + input.charCodeAt(i)) | 0;
  }
  return h;
}

/**
 * Generates a synthetic 5m bar series that drifts toward `anchorPrice` by
 * the end of the series — illustrative only (mirrors the same intent as
 * backtest/generate_synthetic_data.py: never presented as real market
 * history). Used so the setup-detail chart has something to show before
 * a real market-data feed is wired up.
 */
export function generateMockBars(seedKey: string, anchorPrice: number, count = 120): OhlcBar[] {
  const rand = mulberry32(hashSeed(seedKey));
  const bars: OhlcBar[] = [];

  const startPrice = anchorPrice * (1 + (rand() - 0.5) * 0.015);
  let price = startPrice;
  const nowSec = Math.floor(Date.now() / 1000);
  const stepSec = 5 * 60;
  const startTime = nowSec - count * stepSec;

  for (let i = 0; i < count; i++) {
    const progress = i / count;
    const drift = (anchorPrice - startPrice) * (progress > 0.85 ? 0.15 : 0.02);
    const vol = anchorPrice * 0.0009;

    const open = price;
    const close = open + drift + (rand() - 0.5) * vol * 2;
    const high = Math.max(open, close) + rand() * vol;
    const low = Math.min(open, close) - rand() * vol;

    bars.push({
      time: (startTime + i * stepSec) as UTCTimestamp,
      open,
      high,
      low,
      close,
    });

    price = close;
  }

  // Nudge the final close to land close to the anchor so entry/stop/target
  // lines sit in a plausible spot relative to the candles.
  const last = bars[bars.length - 1];
  const correction = anchorPrice - last.close;
  last.close += correction;
  last.high = Math.max(last.high, last.close);
  last.low = Math.min(last.low, last.close);

  return bars;
}
