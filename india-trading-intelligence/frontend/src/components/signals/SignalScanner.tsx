"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { Signal } from "@/lib/types";
import { DirectionTag } from "@/components/ui/DirectionTag";
import { StateBadge } from "@/components/ui/StateBadge";
import { ScoreDisplay } from "@/components/ui/ScoreDisplay";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatPrice, formatRiskReward, timeAgo } from "@/lib/format";
import { cn } from "@/lib/cn";

type SortKey = "updatedAt" | "score" | "riskReward" | "state";

const SORT_LABEL: Record<SortKey, string> = {
  updatedAt: "Updated",
  score: "Score",
  riskReward: "R:R",
  state: "State",
};

function sortSignals(signals: Signal[], key: SortKey, dir: "asc" | "desc"): Signal[] {
  const sorted = [...signals].sort((a, b) => {
    let cmp = 0;
    if (key === "updatedAt") cmp = new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime();
    if (key === "score") cmp = a.score - b.score;
    if (key === "riskReward") cmp = (a.riskReward ?? -Infinity) - (b.riskReward ?? -Infinity);
    if (key === "state") cmp = a.state.localeCompare(b.state);
    return dir === "asc" ? cmp : -cmp;
  });
  return sorted;
}

export function SignalScanner({
  signals,
  emptyTitle = "No signals yet",
  emptyDescription = "No Trade is a valid, normal state.",
}: {
  signals: Signal[];
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  const [sortKey, setSortKey] = useState<SortKey>("updatedAt");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const sorted = useMemo(() => sortSignals(signals, sortKey, sortDir), [signals, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  }

  if (signals.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div>
      {/* Mobile sort control */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-2 md:hidden">
        <span className="text-xs text-text-faint">Sort:</span>
        {(Object.keys(SORT_LABEL) as SortKey[]).map((key) => (
          <button
            key={key}
            onClick={() => toggleSort(key)}
            className={cn(
              "rounded px-2 py-1 text-xs",
              sortKey === key ? "bg-surface-2 text-text" : "text-text-muted"
            )}
          >
            {SORT_LABEL[key]}
            {sortKey === key && (sortDir === "asc" ? " ↑" : " ↓")}
          </button>
        ))}
      </div>

      {/* Mobile: card list */}
      <ul className="divide-y divide-border md:hidden">
        {sorted.map((signal) => (
          <li key={signal.id}>
            <Link href={`/signals/${signal.id}`} className="flex flex-col gap-2 px-4 py-3 active:bg-surface-2/60">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{signal.instrument}</span>
                  <DirectionTag direction={signal.direction} />
                </div>
                <StateBadge state={signal.state} />
              </div>
              <div className="flex items-center justify-between">
                <ScoreDisplay score={signal.score} grade={signal.grade} />
                <span className="font-mono text-xs tabular text-text-muted">{formatRiskReward(signal.riskReward)}</span>
              </div>
              <div className="flex items-center justify-between text-[11px] text-text-faint">
                <span>{signal.methodology}</span>
                <span>{timeAgo(signal.updatedAt)}</span>
              </div>
            </Link>
          </li>
        ))}
      </ul>

      {/* Desktop: dense sortable table */}
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-xs text-text-faint">
              <th className="px-4 py-2 font-medium">Symbol</th>
              <th className="px-4 py-2 font-medium">Direction</th>
              <th className="px-4 py-2 font-medium">Methodology</th>
              <th className="cursor-pointer px-4 py-2 font-medium" onClick={() => toggleSort("score")}>
                Score {sortKey === "score" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="cursor-pointer px-4 py-2 font-medium" onClick={() => toggleSort("state")}>
                State {sortKey === "state" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="px-4 py-2 font-medium">Entry</th>
              <th className="cursor-pointer px-4 py-2 font-medium" onClick={() => toggleSort("riskReward")}>
                R:R {sortKey === "riskReward" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
              <th className="cursor-pointer px-4 py-2 font-medium" onClick={() => toggleSort("updatedAt")}>
                Updated {sortKey === "updatedAt" && (sortDir === "asc" ? "↑" : "↓")}
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sorted.map((signal) => (
              <tr key={signal.id} className="group">
                <td className="px-0 py-0">
                  <Link
                    href={`/signals/${signal.id}`}
                    className="flex items-center px-4 py-2.5 font-medium group-hover:bg-surface-2/60"
                  >
                    {signal.instrument}
                  </Link>
                </td>
                <td className="px-4 py-2.5">
                  <DirectionTag direction={signal.direction} />
                </td>
                <td className="px-4 py-2.5 text-text-muted">{signal.methodology}</td>
                <td className="px-4 py-2.5">
                  <ScoreDisplay score={signal.score} grade={signal.grade} />
                </td>
                <td className="px-4 py-2.5">
                  <StateBadge state={signal.state} />
                </td>
                <td className="px-4 py-2.5 font-mono tabular text-text-muted">{formatPrice(signal.entry)}</td>
                <td className="px-4 py-2.5 font-mono tabular">{formatRiskReward(signal.riskReward)}</td>
                <td className="px-4 py-2.5 whitespace-nowrap text-xs text-text-faint">{timeAgo(signal.updatedAt)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
