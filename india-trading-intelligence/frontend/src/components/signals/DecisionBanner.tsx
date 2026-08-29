import type { Decision } from "@/lib/types";
import { cn } from "@/lib/cn";

const CONFIG: Record<Decision, { label: string; description: string; className: string }> = {
  MANUAL_ENTRY: {
    label: "Manual Entry",
    description: "This setup has met the system's criteria for entry consideration.",
    className: "border-accent/40 bg-accent-bg text-accent",
  },
  REVIEW: {
    label: "Review",
    description: "This setup needs a closer look before any entry decision.",
    className: "border-state-developing/40 bg-state-developing-bg text-state-developing",
  },
};

/**
 * Deliberately unambiguous, and deliberately never phrased as an
 * instruction to trade automatically - Release 1 is manual-execution-only
 * end to end. This banner states what the system concluded; the decision
 * itself always belongs to the trader.
 */
export function DecisionBanner({ decision }: { decision: Decision | null }) {
  // Never default an unknown decision to MANUAL_ENTRY - treat it as
  // needing review, same posture as an explicit REVIEW, just with
  // honest wording that nothing has been evaluated yet.
  if (decision === null) {
    return (
      <div className="rounded-lg border border-border bg-surface-2 p-4">
        <span className="text-sm font-bold uppercase tracking-wide text-text-muted">Not Yet Evaluated</span>
        <p className="mt-1 text-sm text-text">This setup has no confluence summary yet.</p>
        <p className="mt-2 text-xs text-text-muted">
          This platform never places or times orders automatically. Entry, sizing, and timing are your decision to
          make manually.
        </p>
      </div>
    );
  }

  const config = CONFIG[decision];
  return (
    <div className={cn("rounded-lg border p-4", config.className)}>
      <div className="flex items-center gap-2">
        <span className="text-sm font-bold uppercase tracking-wide">{config.label}</span>
      </div>
      <p className="mt-1 text-sm text-text">{config.description}</p>
      <p className="mt-2 text-xs text-text-muted">
        This platform never places or times orders automatically. Entry, sizing, and timing are your decision to make
        manually.
      </p>
    </div>
  );
}
