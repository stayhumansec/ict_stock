export function ReasoningChain({ steps }: { steps: string[] }) {
  if (steps.length === 0) {
    return <p className="text-sm text-text-faint">No reasoning recorded for this setup.</p>;
  }

  return (
    <ol className="flex flex-col gap-3">
      {steps.map((step, i) => (
        <li key={i} className="flex gap-3">
          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-surface-2 font-mono text-[11px] text-text-muted tabular">
            {i + 1}
          </span>
          <p className="text-sm text-text">{step}</p>
        </li>
      ))}
    </ol>
  );
}
