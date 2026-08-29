import { ENABLED_METHODOLOGIES, type MethodologyMode } from "@/lib/types";
import { cn } from "@/lib/cn";

const MODES: MethodologyMode[] = ["SMC", "ICT", "HYBRID"];

/**
 * Shows the full intended architecture (SMC / ICT / Hybrid) with disabled
 * modes visibly grayed out rather than hidden - ICT and Hybrid don't
 * exist yet, but the selector's shape should already reflect where
 * they'll go. Selecting a disabled mode is a no-op.
 */
export function MethodologyTabs({ active = "SMC" }: { active?: MethodologyMode }) {
  return (
    <div className="inline-flex items-center gap-1 rounded-md border border-border bg-surface-2 p-0.5 text-xs">
      {MODES.map((mode) => {
        const enabled = ENABLED_METHODOLOGIES.includes(mode);
        const isActive = mode === active && enabled;
        return (
          <span
            key={mode}
            className={cn(
              "rounded px-2 py-1 font-medium",
              isActive && "bg-surface text-text",
              !isActive && enabled && "text-text-muted",
              !enabled && "cursor-not-allowed text-text-faint"
            )}
            title={enabled ? undefined : `${mode} is not implemented yet`}
          >
            {mode}
          </span>
        );
      })}
    </div>
  );
}
