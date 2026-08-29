export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1 px-4 py-12 text-center">
      <p className="text-sm font-medium text-text-muted">{title}</p>
      {description && <p className="max-w-sm text-xs text-text-faint">{description}</p>}
    </div>
  );
}
