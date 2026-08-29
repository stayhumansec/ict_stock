import type { SignalState } from "@/lib/types";
import { cn } from "@/lib/cn";

// Every class name below is written out literally (never built via string
// concatenation) so Tailwind's static scanner can find and generate it.
const STATE_CONFIG: Record<SignalState, { label: string; fg: string; bg: string; dot: string }> = {
  DEVELOPING: { label: "Developing", fg: "text-state-developing", bg: "bg-state-developing-bg", dot: "bg-state-developing" },
  CONFIRMED: { label: "Confirmed", fg: "text-state-confirmed", bg: "bg-state-confirmed-bg", dot: "bg-state-confirmed" },
  ACTIVE: { label: "Active", fg: "text-state-active", bg: "bg-state-active-bg", dot: "bg-state-active" },
  TARGET_HIT: { label: "Target Hit", fg: "text-state-active", bg: "bg-state-active-bg", dot: "bg-state-active" },
  STOP_HIT: { label: "Stop Hit", fg: "text-bearish", bg: "bg-bearish-bg", dot: "bg-bearish" },
  INVALIDATED: { label: "Invalidated", fg: "text-state-invalidated", bg: "bg-state-invalidated-bg", dot: "bg-state-invalidated" },
  EXPIRED: { label: "Expired", fg: "text-state-expired", bg: "bg-state-expired-bg", dot: "bg-state-expired" },
};

export function StateBadge({ state, className }: { state: SignalState; className?: string }) {
  const config = STATE_CONFIG[state];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        config.fg,
        config.bg,
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", config.dot)} />
      {config.label}
    </span>
  );
}
