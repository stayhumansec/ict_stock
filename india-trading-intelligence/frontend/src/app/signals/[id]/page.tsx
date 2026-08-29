import Link from "next/link";
import { notFound } from "next/navigation";
import { getSignalById } from "@/lib/data-source";
import { DirectionTag } from "@/components/ui/DirectionTag";
import { StateBadge } from "@/components/ui/StateBadge";
import { ScoreDisplay } from "@/components/ui/ScoreDisplay";
import { DataQualityTag } from "@/components/ui/DataQualityTag";
import { Card, CardHeader, CardTitle, CardBody } from "@/components/ui/Card";
import { DecisionBanner } from "@/components/signals/DecisionBanner";
import { TradePlan } from "@/components/signals/TradePlan";
import { StructureRefList } from "@/components/signals/StructureRefList";
import { ReasoningChain } from "@/components/signals/ReasoningChain";
import { SetupChart } from "@/components/chart/SetupChart";
import { formatClock, timeAgo } from "@/lib/format";

export default async function SignalDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const signal = await getSignalById(id);

  if (!signal) notFound();

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4 p-4 md:p-6">
      <Link href="/signals" className="text-xs text-text-faint hover:text-text-muted">
        ← Back to Signal Feed
      </Link>

      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">{signal.instrument}</h1>
        <DirectionTag direction={signal.direction} />
        <StateBadge state={signal.state} />
        <span className="ml-auto text-xs text-text-faint">
          Updated {timeAgo(signal.updatedAt)} · {formatClock(signal.updatedAt)}
        </span>
      </div>

      <DecisionBanner decision={signal.decision} />

      <Card>
        <CardHeader>
          <CardTitle>Trade Plan</CardTitle>
        </CardHeader>
        <CardBody>
          <TradePlan signal={signal} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Chart</CardTitle>
        </CardHeader>
        <CardBody>
          <SetupChart signal={signal} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Why This Setup Exists</CardTitle>
        </CardHeader>
        <CardBody>
          <ReasoningChain steps={signal.reasoningChain} />
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Core Signal</CardTitle>
          </CardHeader>
          <CardBody>
            <StructureRefList refs={signal.coreSignal} tone="core" emptyLabel="No core signal recorded." />
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Confirmations</CardTitle>
          </CardHeader>
          <CardBody>
            <StructureRefList refs={signal.confirmations} tone="confirm" emptyLabel="No additional confirmations." />
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Conflicting Context</CardTitle>
        </CardHeader>
        <CardBody>
          <StructureRefList
            refs={signal.conflicts}
            tone="conflict"
            emptyLabel="No conflicting context identified for this setup."
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Signal Metadata</CardTitle>
        </CardHeader>
        <CardBody className="flex flex-wrap items-center gap-3">
          <ScoreDisplay score={signal.score} grade={signal.grade} />
          <DataQualityTag quality={signal.dataQuality} />
          <span className="rounded border border-border px-2 py-0.5 text-xs text-text-muted">
            {signal.methodology}
          </span>
          <span className="text-xs text-text-faint">Created {timeAgo(signal.createdAt)}</span>
        </CardBody>
      </Card>
    </div>
  );
}
