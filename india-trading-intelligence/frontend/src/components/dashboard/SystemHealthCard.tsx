import type { SystemHealth } from "@/lib/types";
import { ConnectionDot } from "@/components/ui/ConnectionDot";
import { timeAgo } from "@/lib/format";

function Row({ label, ok, value }: { label: string; ok: boolean; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="flex items-center gap-1.5 text-xs font-medium">
        <ConnectionDot connected={ok} />
        {value}
      </span>
    </div>
  );
}

// Automation being off is correct-by-design in Release 1, not a fault -
// a red dot there would misleadingly read as an error. Use a neutral
// indicator instead of the binary connected/disconnected dot.
function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-xs text-text-muted">{label}</span>
      <span className="flex items-center gap-1.5 text-xs font-medium text-text-muted">
        <span className="h-2 w-2 rounded-full bg-text-faint" />
        {value}
      </span>
    </div>
  );
}

export function SystemHealthCard({ health }: { health: SystemHealth }) {
  return (
    <div className="flex flex-col divide-y divide-border">
      <Row label="Data feed" ok={health.dataFeedConnected} value={health.dataFeedConnected ? "Connected" : "Disconnected"} />
      <Row label="Last tick" ok={health.dataFeedConnected} value={timeAgo(health.lastTickAt)} />
      <Row label="Telegram" ok={health.telegramConfigured} value={health.telegramConfigured ? "Configured" : "Not configured"} />
      <InfoRow label="Automation" value="Disabled (manual execution only)" />
    </div>
  );
}
