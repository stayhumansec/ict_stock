import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";

// Full Journal screen (past signals + outcomes table) is priority #4,
// built after Dashboard and Signal Feed are confirmed. Release 1 has no
// persistence yet, so this correctly has nothing to show.
export default function JournalPage() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4 p-4 md:p-6">
      <h1 className="text-base font-semibold">Journal</h1>
      <Card>
        <CardHeader>
          <CardTitle>Past Signals &amp; Outcomes</CardTitle>
        </CardHeader>
        <EmptyState
          title="No journal entries yet"
          description="Release 1 has no trade persistence — this table will populate once outcomes are recorded."
        />
      </Card>
    </div>
  );
}
