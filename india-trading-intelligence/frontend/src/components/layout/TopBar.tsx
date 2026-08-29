import { ThemeToggle } from "./ThemeToggle";

export function TopBar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-4 md:px-6">
      <div className="flex items-center gap-2 md:hidden">
        <span className="h-2 w-2 rounded-full bg-accent" />
        <span className="text-sm font-semibold tracking-tight">SMC Terminal</span>
      </div>
      <div className="hidden text-xs text-text-faint md:block">Manual execution only — no automated orders are placed.</div>
      <ThemeToggle />
    </header>
  );
}
