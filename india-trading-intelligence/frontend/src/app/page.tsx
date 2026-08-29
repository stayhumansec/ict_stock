import { getActiveSignals, getMarketOverview, getSystemHealth } from "@/lib/data-source";
import { MarketOverviewCard } from "@/components/dashboard/MarketOverviewCard";
import { ActiveSignalsList } from "@/components/dashboard/ActiveSignalsList";
import { SystemHealthCard } from "@/components/dashboard/SystemHealthCard";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { MethodologyTabs } from "@/components/ui/MethodologyTabs";

export default async function DashboardPage() {
  const [overview, activeSignals, health] = await Promise.all([
    getMarketOverview(),
    getActiveSignals(),
    getSystemHealth(),
  ]);

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold">Dashboard</h1>
        <MethodologyTabs />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {overview.map((o) => (
          <MarketOverviewCard key={o.instrument} overview={o} />
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Active &amp; Developing Setups</CardTitle>
          <span className="text-xs text-text-faint">{activeSignals.length}</span>
        </CardHeader>
        <ActiveSignalsList signals={activeSignals} />
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>System Health</CardTitle>
        </CardHeader>
        <div className="px-4 py-1">
          <SystemHealthCard health={health} />
        </div>
      </Card>
    </div>
  );
}
