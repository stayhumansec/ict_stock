import type { StructureReference } from "@/lib/types";
import { formatPrice } from "@/lib/format";
import { cn } from "@/lib/cn";

/**
 * Renders a list of structural references (core signal / confirmations /
 * conflicts). `tone` picks the accent color so the same component reads
 * differently for "what triggered this" vs "what agrees" vs "what
 * disagrees" without three near-duplicate components.
 */
export function StructureRefList({
  refs,
  tone,
  emptyLabel,
}: {
  refs: StructureReference[];
  tone: "core" | "confirm" | "conflict";
  emptyLabel: string;
}) {
  if (refs.length === 0) {
    return <p className="text-sm text-text-faint">{emptyLabel}</p>;
  }

  const dotClass = tone === "core" ? "bg-state-developing" : tone === "confirm" ? "bg-state-confirmed" : "bg-state-invalidated";

  return (
    <ul className="flex flex-col gap-2">
      {refs.map((ref, i) => (
        <li key={i} className="flex items-start gap-2.5">
          <span className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", dotClass)} />
          <div className="flex min-w-0 flex-col">
            <div className="flex items-baseline gap-2">
              <span className="text-sm font-medium">{ref.kind}</span>
              <span className="font-mono text-xs text-text-muted tabular">{formatPrice(ref.price)}</span>
            </div>
            {ref.note && <p className="text-xs text-text-muted">{ref.note}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}
