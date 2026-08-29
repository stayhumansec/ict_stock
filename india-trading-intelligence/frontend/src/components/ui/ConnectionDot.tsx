import { cn } from "@/lib/cn";

export function ConnectionDot({ connected, className }: { connected: boolean; className?: string }) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        connected ? "bg-bullish" : "bg-bearish",
        className
      )}
      aria-label={connected ? "Connected" : "Disconnected"}
    />
  );
}
