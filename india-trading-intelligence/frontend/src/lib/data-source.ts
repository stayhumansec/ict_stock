/**
 * Data access layer. Every function is async and returns plain data -
 * components never know whether the data came from the mock layer below
 * or a real backend call. Swap the bodies of these functions for `fetch`
 * calls against the real API once one exists; nothing else in the app
 * needs to change.
 */

import { MOCK_MARKET_OVERVIEW, MOCK_SIGNALS, MOCK_SYSTEM_HEALTH } from "./mock-data";
import type { MarketOverview, Signal, SignalState, SystemHealth } from "./types";

const TERMINAL_STATES: SignalState[] = ["TARGET_HIT", "STOP_HIT", "INVALIDATED", "EXPIRED"];

export async function getMarketOverview(): Promise<MarketOverview[]> {
  return MOCK_MARKET_OVERVIEW;
}

export async function getSystemHealth(): Promise<SystemHealth> {
  return MOCK_SYSTEM_HEALTH;
}

export async function getSignals(): Promise<Signal[]> {
  return MOCK_SIGNALS;
}

export async function getActiveSignals(): Promise<Signal[]> {
  const signals = await getSignals();
  return signals.filter((s) => s.state === "DEVELOPING" || s.state === "CONFIRMED" || s.state === "ACTIVE");
}

export async function getSignalById(id: string): Promise<Signal | null> {
  const signals = await getSignals();
  return signals.find((s) => s.id === id) ?? null;
}

/** Resolved signals for the Journal screen - Release 1 has no trade
 * persistence yet, so this reflects only what's in the current session's
 * signal list, not a durable history. */
export async function getResolvedSignals(): Promise<Signal[]> {
  const signals = await getSignals();
  return signals.filter((s) => TERMINAL_STATES.includes(s.state));
}
