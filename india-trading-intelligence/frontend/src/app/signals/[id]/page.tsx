import { notFound } from "next/navigation";
import { getSignalById } from "@/lib/data-source";
import { DirectionTag } from "@/components/ui/DirectionTag";
import { StateBadge } from "@/components/ui/StateBadge";

// Placeholder only - the full Setup Detail screen (core signal, conflicts,
// entry/stop/target, reasoning chain, chart, decision label) is the next
// checkpoint after Dashboard + Signal Feed are confirmed.
export default async function SignalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const signal = await getSignalById(id);

  if (!signal) notFound();

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-4 md:p-6">
      <div className="flex items-center gap-2">
        <h1 className="text-base font-semibold">{signal.instrument}</h1>
        <DirectionTag direction={signal.direction} />
        <StateBadge state={signal.state} />
      </div>
      <div className="rounded-lg border border-border bg-surface p-4 text-sm text-text-muted">
        Full setup detail (reasoning chain, entry/stop/target, chart, decision label) is coming in the next
        checkpoint.
      </div>
    </div>
  );
}
