import type { MarketOverview } from "@/lib/types";
import { formatPct, formatPrice } from "@/lib/format";
import { RegimeTag, SessionTag } from "@/components/ui/RegimeTag";
import { cn } from "@/lib/cn";

export function MarketOverviewCard({ overview }: { overview: MarketOverview }) {
  const up = overview.changePct >= 0;
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{overview.instrument}</span>
        <SessionTag session={overview.session} />
      </div>
      <div className="flex items-baseline gap-2">
        <span className="font-mono text-2xl font-semibold tabular">{formatPrice(overview.lastPrice)}</span>
        <span className={cn("font-mono text-sm tabular", up ? "text-bullish" : "text-bearish")}>
          {formatPct(overview.changePct, { signed: true })}
        </span>
      </div>
      <div>
        <RegimeTag regime={overview.regime} />
      </div>
    </div>
  );
}
