import { getSystemHealth } from "@/lib/data-source";
import { Card, CardHeader, CardTitle, CardBody } from "@/components/ui/Card";
import { ConnectionDot } from "@/components/ui/ConnectionDot";
import { MethodologyTabs } from "@/components/ui/MethodologyTabs";
import { NotificationPreferences } from "@/components/settings/NotificationPreferences";

export default async function SettingsPage() {
  const health = await getSystemHealth();

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4 md:p-6">
      <h1 className="text-base font-semibold">Settings</h1>

      <Card>
        <CardHeader>
          <CardTitle>Telegram</CardTitle>
        </CardHeader>
        <CardBody className="flex items-center gap-2 text-sm">
          <ConnectionDot connected={health.telegramConfigured} />
          {health.telegramConfigured ? "Configured" : "Not configured"}
          <span className="ml-auto text-xs text-text-faint">
            {health.telegramConfigured ? "Alerts deliver to your bot chat" : "Set TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"}
          </span>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notification Preferences</CardTitle>
        </CardHeader>
        <CardBody>
          <NotificationPreferences />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Methodology</CardTitle>
        </CardHeader>
        <CardBody className="flex items-center justify-between gap-3">
          <p className="text-xs text-text-faint">Only SMC is implemented in Release 1.</p>
          <MethodologyTabs />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Automation</CardTitle>
        </CardHeader>
        <CardBody className="text-sm text-text-muted">
          Automated order placement is disabled and not configurable — Release 1 is manual-execution-only by design.
        </CardBody>
      </Card>
    </div>
  );
}
