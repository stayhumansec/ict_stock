import { getSignals } from "@/lib/data-source";
import { SignalScanner } from "@/components/signals/SignalScanner";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { MethodologyTabs } from "@/components/ui/MethodologyTabs";

export default async function SignalsPage() {
  const signals = await getSignals();

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold">Signal Feed</h1>
        <MethodologyTabs />
      </div>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>All Signals</CardTitle>
          <span className="text-xs text-text-faint">{signals.length}</span>
        </CardHeader>
        <SignalScanner signals={signals} />
      </Card>
    </div>
  );
}
