import type { Signal } from "@/lib/types";
import { formatPrice, formatRiskReward } from "@/lib/format";

function Stat({ label, value, valueClassName }: { label: string; value: string; valueClassName?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[11px] uppercase tracking-wide text-text-faint">{label}</span>
      <span className={`font-mono text-lg font-semibold tabular ${valueClassName ?? ""}`}>{value}</span>
    </div>
  );
}

export function TradePlan({ signal }: { signal: Signal }) {
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Stat label="Entry" value={formatPrice(signal.entry)} />
      <Stat label="Stop" value={formatPrice(signal.stopLoss)} valueClassName="text-bearish" />
      <Stat
        label={signal.targets.length > 1 ? "Targets" : "Target"}
        value={signal.targets.length > 0 ? signal.targets.map(formatPrice).join(" / ") : "—"}
        valueClassName="text-bullish"
      />
      <Stat label="Risk:Reward" value={formatRiskReward(signal.riskReward)} />
    </div>
  );
}
