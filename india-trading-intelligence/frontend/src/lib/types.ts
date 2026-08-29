/**
 * Shared domain types for the dashboard. These mirror the backend shapes
 * (backend/smc/models.py, backend/signals/signal.py) where they exist
 * today. Some fields here are richer than the current Release 1 backend
 * (e.g. TARGET_HIT/STOP_HIT outcome states, which need trade persistence
 * that doesn't exist until a later checkpoint) — those are marked below
 * so the mock layer and a future real API both know what they owe.
 */

export type Instrument = "NIFTY" | "BANKNIFTY";

export type Direction = "BULLISH" | "BEARISH";

export type MethodologyMode = "SMC" | "ICT" | "HYBRID";

/** Only SMC is implemented in Release 1 — ICT/HYBRID are shown disabled,
 * never hidden, so the intended architecture stays visible. */
export const ENABLED_METHODOLOGIES: MethodologyMode[] = ["SMC"];

/**
 * Signal lifecycle state.
 *
 * DEVELOPING / CONFIRMED / TRIGGERED / INVALIDATED / EXPIRED map directly
 * to backend/signals/signal.py's SignalState.
 *
 * ACTIVE, TARGET_HIT and STOP_HIT are outcome-tracking states this UI
 * needs for the scanner and journal, but the backend does not persist
 * trade outcomes yet (no database wiring until past checkpoint 5) — until
 * then these three are mock-only and a real API may simply never emit
 * them.
 */
export type SignalState =
  | "DEVELOPING"
  | "CONFIRMED"
  | "ACTIVE"
  | "TARGET_HIT"
  | "STOP_HIT"
  | "INVALIDATED"
  | "EXPIRED";

export type DataQuality = "HIGH" | "MEDIUM" | "LOW";

export type Decision = "REVIEW" | "MANUAL_ENTRY";

export type MarketRegime = "TRENDING" | "RANGING" | "BREAKOUT" | "VOLATILE";

export type MarketSession =
  | "PRE_OPEN"
  | "MORNING"
  | "MIDDAY"
  | "AFTERNOON"
  | "PRE_CAS"
  | "CAS"
  | "CLOSED";

export interface StructureReference {
  /** e.g. "BOS", "CHoCH", "MSS", "FVG_BULLISH", "ORDER_BLOCK_BEARISH" */
  kind: string;
  price: number;
  note?: string;
}

export interface Signal {
  id: string;
  instrument: Instrument;
  direction: Direction;
  methodology: MethodologyMode;
  state: SignalState;
  /** Structured composite score (0-100). Never a win-probability. */
  score: number;
  grade: "A" | "B" | "C";
  createdAt: string; // ISO timestamp
  updatedAt: string; // ISO timestamp

  entry: number | null;
  stopLoss: number | null;
  targets: number[];
  riskReward: number | null;

  /** The core structural event(s) that triggered this signal. */
  coreSignal: StructureReference[];
  /** Additional context that agrees with the core signal. */
  confirmations: StructureReference[];
  /** Context that disagrees with the setup - shown, never hidden. */
  conflicts: StructureReference[];

  /** Plain-language reasoning chain, in order, e.g.
   * ["Sell-side liquidity swept below prior day low", "Bullish MSS confirmed", "Displacement", "FVG retest"] */
  reasoningChain: string[];

  dataQuality: DataQuality;
  decision: Decision;
}

export interface MarketOverview {
  instrument: Instrument;
  lastPrice: number;
  changePct: number;
  regime: MarketRegime;
  session: MarketSession;
}

export interface SystemHealth {
  dataFeedConnected: boolean;
  lastTickAt: string | null; // ISO timestamp
  telegramConfigured: boolean;
  automationEnabled: boolean; // must always be false in Release 1
}
