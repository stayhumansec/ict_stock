"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

type Severity = "INFO" | "SETUP" | "ACTIONABLE" | "WARNING" | "CRITICAL";
type Instrument = "NIFTY" | "BANKNIFTY";

const SEVERITIES: { key: Severity; label: string; description: string }[] = [
  { key: "INFO", label: "Info", description: "Context updates, e.g. \"No Trade\" summaries" },
  { key: "SETUP", label: "Setup", description: "A signal enters DEVELOPING or CONFIRMED" },
  { key: "ACTIONABLE", label: "Actionable", description: "A signal reaches TRIGGERED / manual entry point" },
  { key: "WARNING", label: "Warning", description: "Risk gate blocked, data unavailable, etc." },
  { key: "CRITICAL", label: "Critical", description: "Engine or connectivity failure" },
];

const INSTRUMENTS: Instrument[] = ["NIFTY", "BANKNIFTY"];

const STORAGE_KEY = "notificationPrefs";

interface Prefs {
  severities: Severity[];
  instruments: Instrument[];
}

const DEFAULT_PREFS: Prefs = {
  severities: ["SETUP", "ACTIONABLE", "WARNING", "CRITICAL"],
  instruments: ["NIFTY", "BANKNIFTY"],
};

function loadPrefs(): Prefs {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFS;
    const parsed = JSON.parse(raw);
    return {
      severities: Array.isArray(parsed.severities) ? parsed.severities : DEFAULT_PREFS.severities,
      instruments: Array.isArray(parsed.instruments) ? parsed.instruments : DEFAULT_PREFS.instruments,
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: () => void; label: string; description?: string }) {
  return (
    <button
      type="button"
      onClick={onChange}
      className="flex w-full items-center justify-between gap-3 py-2.5 text-left"
    >
      <div className="flex flex-col">
        <span className="text-sm">{label}</span>
        {description && <span className="text-xs text-text-faint">{description}</span>}
      </div>
      <span
        className={cn(
          "relative h-5 w-9 shrink-0 rounded-full transition-colors",
          checked ? "bg-accent" : "bg-surface-2 border border-border-strong"
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white transition-transform",
            checked ? "translate-x-[18px]" : "translate-x-0"
          )}
        />
      </span>
    </button>
  );
}

export function NotificationPreferences() {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // Syncing from localStorage (unavailable during SSR) is the one
    // legitimate reason to setState directly in a mount effect here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPrefs(loadPrefs());
    setLoaded(true);
  }, []);

  useEffect(() => {
    if (!loaded) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  }, [prefs, loaded]);

  function toggleSeverity(key: Severity) {
    setPrefs((p) => ({
      ...p,
      severities: p.severities.includes(key) ? p.severities.filter((s) => s !== key) : [...p.severities, key],
    }));
  }

  function toggleInstrument(key: Instrument) {
    setPrefs((p) => ({
      ...p,
      instruments: p.instruments.includes(key) ? p.instruments.filter((s) => s !== key) : [...p.instruments, key],
    }));
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-text-faint">Alert on</p>
        <div className="divide-y divide-border">
          {SEVERITIES.map((s) => (
            <Toggle
              key={s.key}
              checked={prefs.severities.includes(s.key)}
              onChange={() => toggleSeverity(s.key)}
              label={s.label}
              description={s.description}
            />
          ))}
        </div>
      </div>

      <div>
        <p className="mb-1 text-xs font-medium uppercase tracking-wide text-text-faint">Instruments</p>
        <div className="divide-y divide-border">
          {INSTRUMENTS.map((i) => (
            <Toggle key={i} checked={prefs.instruments.includes(i)} onChange={() => toggleInstrument(i)} label={i} />
          ))}
        </div>
      </div>

      <p className="text-[11px] text-text-faint">
        Stored on this device only — Release 1 has no account sync or backend settings API yet.
      </p>
    </div>
  );
}
