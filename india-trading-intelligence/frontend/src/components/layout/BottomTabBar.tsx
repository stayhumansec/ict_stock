"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";
import { NAV_ITEMS } from "./nav-items";
import { NAV_ICONS } from "./icons";

export function BottomTabBar() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-20 flex border-t border-border bg-surface md:hidden">
      {NAV_ITEMS.map((item) => {
        const Icon = NAV_ICONS[item.href];
        const active = pathname === item.href;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex flex-1 flex-col items-center gap-0.5 py-2 text-[11px]",
              active ? "text-accent" : "text-text-faint"
            )}
          >
            <Icon />
            {item.shortLabel}
          </Link>
        );
      })}
    </nav>
  );
}
