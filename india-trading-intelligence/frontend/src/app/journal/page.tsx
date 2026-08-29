import { getResolvedSignals } from "@/lib/data-source";
import { SignalScanner } from "@/components/signals/SignalScanner";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";

export default async function JournalPage() {
  const resolved = await getResolvedSignals();

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-base font-semibold">Journal</h1>
        <p className="text-xs text-text-faint">
          Resolved signals from the current session only — Release 1 has no historical trade persistence yet, so
          this list resets when the backend restarts.
        </p>
      </div>

      <Card className="overflow-hidden">
        <CardHeader>
          <CardTitle>Past Signals &amp; Outcomes</CardTitle>
          <span className="text-xs text-text-faint">{resolved.length}</span>
        </CardHeader>
        <SignalScanner
          signals={resolved}
          emptyTitle="No journal entries yet"
          emptyDescription="Resolved signals (target hit, stop hit, invalidated, or expired) will appear here."
        />
      </Card>
    </div>
  );
}
