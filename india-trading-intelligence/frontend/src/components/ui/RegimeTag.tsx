import type { MarketRegime, MarketSession } from "@/lib/types";
import { cn } from "@/lib/cn";

const REGIME_CONFIG: Record<MarketRegime, { label: string; className: string }> = {
  TRENDING: { label: "Trending", className: "text-bullish bg-bullish-bg" },
  RANGING: { label: "Ranging", className: "text-text-muted bg-surface-2" },
  BREAKOUT: { label: "Breakout", className: "text-state-confirmed bg-state-confirmed-bg" },
  VOLATILE: { label: "Volatile", className: "text-state-developing bg-state-developing-bg" },
};

export function RegimeTag({ regime, className }: { regime: MarketRegime; className?: string }) {
  const config = REGIME_CONFIG[regime];
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium", config.className, className)}>
      {config.label}
    </span>
  );
}

const SESSION_LABEL: Record<MarketSession, string> = {
  PRE_OPEN: "Pre-open",
  MORNING: "Morning",
  MIDDAY: "Midday",
  AFTERNOON: "Afternoon",
  PRE_CAS: "Pre-CAS",
  CAS: "CAS",
  CLOSED: "Closed",
};

export function SessionTag({ session, className }: { session: MarketSession; className?: string }) {
  return (
    <span className={cn("inline-flex items-center rounded border border-border px-2 py-0.5 text-xs text-text-muted", className)}>
      {SESSION_LABEL[session]}
    </span>
  );
}
