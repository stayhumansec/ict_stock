"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { NAV_ITEMS } from "./nav-items";
import { NAV_ICONS } from "./icons";

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-56 shrink-0 flex-col border-r border-border bg-surface md:flex">
      <div className="flex h-14 items-center gap-2 border-b border-border px-4">
        <span className="h-2 w-2 rounded-full bg-accent" />
        <span className="text-sm font-semibold tracking-tight">SMC Terminal</span>
      </div>
      <nav className="flex flex-col gap-0.5 p-2">
        {NAV_ITEMS.map((item) => {
          const Icon = NAV_ICONS[item.href];
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                active ? "bg-surface-2 text-text" : "text-text-muted hover:text-text hover:bg-surface-2/60"
              )}
            >
              <Icon className={cn(active ? "text-accent" : "text-text-faint")} />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
