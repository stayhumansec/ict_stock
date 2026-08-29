import { getSystemHealth } from "@/lib/data-source";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { ConnectionDot } from "@/components/ui/ConnectionDot";

// Minimal Settings placeholder (priority #5). Full notification-preference
// controls come after Dashboard + Signal Feed are confirmed.
export default async function SettingsPage() {
  const health = await getSystemHealth();

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4 md:p-6">
      <h1 className="text-base font-semibold">Settings</h1>
      <Card>
        <CardHeader>
          <CardTitle>Telegram</CardTitle>
        </CardHeader>
        <div className="flex items-center gap-2 px-4 py-3 text-sm">
          <ConnectionDot connected={health.telegramConfigured} />
          {health.telegramConfigured ? "Configured" : "Not configured"}
        </div>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Notification Preferences</CardTitle>
        </CardHeader>
        <div className="px-4 py-3 text-sm text-text-muted">Coming in a later checkpoint.</div>
      </Card>
    </div>
  );
}
