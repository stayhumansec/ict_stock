import type { DataQuality } from "@/lib/types";
import { cn } from "@/lib/cn";

const CONFIG: Record<DataQuality, { label: string; className: string }> = {
  HIGH: { label: "High", className: "text-bullish bg-bullish-bg" },
  MEDIUM: { label: "Medium", className: "text-state-developing bg-state-developing-bg" },
  LOW: { label: "Low", className: "text-bearish bg-bearish-bg" },
};

export function DataQualityTag({ quality, className }: { quality: DataQuality | null; className?: string }) {
  if (quality === null) {
    return <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs text-text-faint", className)}>Data quality: —</span>;
  }
  const config = CONFIG[quality];
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium", config.className, className)}>
      Data quality: {config.label}
    </span>
  );
}
