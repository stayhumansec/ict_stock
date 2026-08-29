/**
 * Data access layer. Every function is async and returns plain data -
 * components never know whether the data came from a real API call or
 * the mock fallback below.
 *
 * Signals/journal/system-health call the real backend
 * (backend/api/server.py) at API_BASE_URL. Market overview stays mocked
 * everywhere, including against a live backend - there is no market-
 * regime or trading-session classifier in this project (out of
 * BUILD_SPEC.md's scope), so there is nothing real to fetch yet; see
 * lib/types.ts's MarketOverview doc comment.
 *
 * If the API is unreachable (no backend running, e.g. a Vercel preview
 * with nothing behind it), each function falls back to mock data with a
 * console warning rather than crashing the page - useful for demoing the
 * UI standalone, never silently pretended to be real in the data itself.
 */

import { MOCK_MARKET_OVERVIEW, MOCK_SIGNALS, MOCK_SYSTEM_HEALTH } from "./mock-data";
import type { MarketOverview, Signal, SystemHealth } from "./types";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new Error(`${path} returned HTTP ${res.status}`);
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`[data-source] Falling back to mock data - could not reach API at ${API_BASE_URL}${path}:`, err);
    return undefined as unknown as T; // signals "use the mock fallback" to callers below
  }
}

export async function getMarketOverview(): Promise<MarketOverview[]> {
  return MOCK_MARKET_OVERVIEW;
}

export async function getSystemHealth(): Promise<SystemHealth> {
  const health = await fetchJson<SystemHealth>("/api/system-health");
  return health ?? MOCK_SYSTEM_HEALTH;
}

export async function getSignals(): Promise<Signal[]> {
  const signals = await fetchJson<Signal[]>("/api/signals");
  return signals ?? MOCK_SIGNALS;
}

export async function getActiveSignals(): Promise<Signal[]> {
  const signals = await fetchJson<Signal[]>("/api/signals/active");
  if (signals !== undefined) return signals ?? [];
  const mock = await getSignals();
  return mock.filter((s) => s.state === "DEVELOPING" || s.state === "CONFIRMED" || s.state === "ACTIVE");
}

export async function getSignalById(id: string): Promise<Signal | null> {
  const signal = await fetchJson<Signal>(`/api/signals/${encodeURIComponent(id)}`);
  if (signal !== undefined) return signal;
  const mock = await getSignals();
  return mock.find((s) => s.id === id) ?? null;
}

/** Resolved signals for the Journal screen. */
export async function getResolvedSignals(): Promise<Signal[]> {
  const signals = await fetchJson<Signal[]>("/api/signals/resolved");
  if (signals !== undefined) return signals ?? [];
  const mock = await getSignals();
  const terminal: Signal["state"][] = ["TARGET_HIT", "STOP_HIT", "INVALIDATED", "EXPIRED"];
  return mock.filter((s) => terminal.includes(s.state));
}
