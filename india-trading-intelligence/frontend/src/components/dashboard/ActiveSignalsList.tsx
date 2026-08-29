import Link from "next/link";
import type { Signal } from "@/lib/types";
import { DirectionTag } from "@/components/ui/DirectionTag";
import { StateBadge } from "@/components/ui/StateBadge";
import { ScoreDisplay } from "@/components/ui/ScoreDisplay";
import { EmptyState } from "@/components/ui/EmptyState";
import { timeAgo } from "@/lib/format";

export function ActiveSignalsList({ signals }: { signals: Signal[] }) {
  if (signals.length === 0) {
    return (
      <EmptyState
        title="No active setups"
        description="No Trade is a valid, normal state — the engine isn't tuned to maximize signal count."
      />
    );
  }

  return (
    <ul className="divide-y divide-border">
      {signals.map((signal) => (
        <li key={signal.id}>
          <Link
            href={`/signals/${signal.id}`}
            className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-2/60 transition-colors"
          >
            <div className="flex min-w-0 flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold">{signal.instrument}</span>
                <DirectionTag direction={signal.direction} />
              </div>
              <p className="truncate text-xs text-text-muted">{signal.reasoningChain[0]}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <StateBadge state={signal.state} />
              <div className="flex items-center gap-2">
                <ScoreDisplay score={signal.score} grade={signal.grade} />
              </div>
              <span className="text-[11px] text-text-faint">{timeAgo(signal.updatedAt)}</span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
