import { cn } from "@/lib/cn";

/**
 * A structured composite score (0-100) and discrete grade bucket.
 * Deliberately NOT styled or labeled as a probability/confidence percent
 * — see BUILD_SPEC.md principle #6. The bar is a visual summary of the
 * same structured number, nothing more.
 */
export function ScoreDisplay({ score, grade, className }: { score: number; grade: "A" | "B" | "C"; className?: string }) {
  const gradeColor = grade === "A" ? "text-bullish" : grade === "B" ? "text-state-confirmed" : "text-text-muted";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className={cn("font-mono text-sm font-semibold tabular", gradeColor)}>{grade}</span>
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-2">
        <div
          className={cn("h-full rounded-full", grade === "A" ? "bg-bullish" : grade === "B" ? "bg-state-confirmed" : "bg-text-faint")}
          style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
        />
      </div>
      <span className="font-mono text-xs text-text-muted tabular">{score}</span>
    </div>
  );
}
