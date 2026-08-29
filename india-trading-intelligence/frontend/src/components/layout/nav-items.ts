export interface NavItem {
  href: string;
  label: string;
  shortLabel: string;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Dashboard", shortLabel: "Home" },
  { href: "/signals", label: "Signal Feed", shortLabel: "Signals" },
  { href: "/journal", label: "Journal", shortLabel: "Journal" },
  { href: "/settings", label: "Settings", shortLabel: "Settings" },
];
