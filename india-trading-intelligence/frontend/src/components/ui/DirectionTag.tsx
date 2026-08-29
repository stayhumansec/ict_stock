import type { Direction } from "@/lib/types";
import { cn } from "@/lib/cn";

export function DirectionTag({ direction, className }: { direction: Direction; className?: string }) {
  const bullish = direction === "BULLISH";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold tabular",
        bullish ? "text-bullish bg-bullish-bg" : "text-bearish bg-bearish-bg",
        className
      )}
    >
      {bullish ? "▲ LONG" : "▼ SHORT"}
    </span>
  );
}
