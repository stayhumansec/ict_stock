"""Loads synthetic bars, runs SMCEngine, prints a human-checkable event log,
and saves a simple price+event chart.

Usage: python -m backtest.run_backtest
"""

from __future__ import annotations

import argparse
from typing import List

from backend.smc.config import SMCConfig
from backend.smc.engine import SMCEngine
from backend.smc.models import Bar, EngineResult
from backtest.generate_synthetic_data import generate_synthetic_bars


def print_event_log(bars: List[Bar], result: EngineResult) -> None:
    print("\n=== SWINGS (external only, internal omitted for brevity) ===")
    for s in sorted(result.external_swings, key=lambda s: s.confirmed_index):
        print(f"  [{s.confirmed_index:4d}] {s.series:8s} {s.kind.value:4s} @ {s.price:.2f} (formed @ {s.formed_index})")

    print(f"\n  internal swing count: {len(result.internal_swings)}")
    print(f"  external swing count: {len(result.external_swings)}")

    print("\n=== STRUCTURE EVENTS ===")
    for e in sorted(result.structure_events, key=lambda e: e.confirmed_index):
        ts = bars[e.confirmed_index].timestamp
        note = f" ({e.note})" if e.note else ""
        print(f"  [{e.confirmed_index:4d} {ts:%Y-%m-%d %H:%M}] {e.event_type.value:14s} {e.direction.value:8s} ref={e.reference_price:.2f}{note}")

    print(f"\n  total structure events: {len(result.structure_events)}")

    print("\n=== LIQUIDITY SWEEPS ===")
    for sw in sorted(result.liquidity_sweeps, key=lambda s: s.swept_index):
        ts = bars[sw.swept_index].timestamp
        print(
            f"  [{sw.swept_index:4d} {ts:%Y-%m-%d %H:%M}] {sw.pool_type.value:14s} "
            f"dir={sw.direction.value:8s} rejection={sw.rejection!s:5s} follow_through={sw.follow_through.value}"
        )
    print(f"\n  total sweeps: {len(result.liquidity_sweeps)}")

    print("\n=== DISPLACEMENT EVENTS ===")
    for d in result.displacement_events:
        ts = bars[d.index].timestamp
        print(f"  [{d.index:4d} {ts:%Y-%m-%d %H:%M}] {d.direction.value:8s} range={d.range_:.2f} atr={d.atr:.2f}")
    print(f"\n  total displacement events: {len(result.displacement_events)}")

    print("\n=== ZONES (FVG + Order Blocks) ===")
    for z in sorted(result.zones, key=lambda z: z.confirmed_index):
        reclass = f" (reclassified from {z.reclassified_from.value})" if z.reclassified_from else ""
        print(
            f"  [{z.confirmed_index:4d}] {z.kind.value:20s} [{z.bottom:.2f}, {z.top:.2f}] "
            f"state={z.state.value}{reclass}"
        )
    print(f"\n  total zones: {len(result.zones)}")

    print("\n=== SANITY SUMMARY ===")
    n_bars = len(bars)
    print(f"  bars processed: {n_bars}")
    print(f"  structure events / 100 bars: {100 * len(result.structure_events) / n_bars:.1f}")
    if len(result.structure_events) > n_bars / 5:
        print("  WARNING: structure event count looks high relative to bar count — check de-duplication.")
    else:
        print("  event density looks reasonable (tens, not hundreds, per few hundred bars).")


def save_chart(bars: List[Bar], result: EngineResult, out_path: str) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print(f"\n[chart] matplotlib not installed — skipping chart, event log above is authoritative.")
        return

    closes = [b.close for b in bars]
    xs = list(range(len(bars)))

    fig, ax = plt.subplots(figsize=(16, 7))
    ax.plot(xs, closes, color="black", linewidth=0.8, label="close")

    colors = {
        "BOS": "tab:blue",
        "CHOCH": "tab:orange",
        "CHOCH_FAILED": "tab:orange",
        "MSS": "tab:red",
        "MSS_FAILED": "tab:red",
    }
    markers = {
        "BOS": "^",
        "CHOCH": "o",
        "CHOCH_FAILED": "x",
        "MSS": "*",
        "MSS_FAILED": "x",
    }
    seen_labels = set()
    for e in result.structure_events:
        label = e.event_type.value if e.event_type.value not in seen_labels else None
        seen_labels.add(e.event_type.value)
        ax.scatter(
            e.confirmed_index,
            bars[e.confirmed_index].close,
            color=colors.get(e.event_type.value, "gray"),
            marker=markers.get(e.event_type.value, "o"),
            s=60,
            label=label,
            zorder=5,
        )

    for sw in result.liquidity_sweeps:
        ax.scatter(sw.swept_index, sw.swept_price, color="purple", marker="v", s=30, alpha=0.6, zorder=4)

    ax.set_title("SMC Engine — Synthetic Backtest Event Log")
    ax.set_xlabel("bar index")
    ax.set_ylabel("price")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    print(f"\n[chart] saved to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SMC engine against generated synthetic data.")
    parser.add_argument("--n-bars", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--chart-out", type=str, default="backtest/output_chart.png")
    args = parser.parse_args()

    bars = generate_synthetic_bars(seed=args.seed, n_bars=args.n_bars)
    config = SMCConfig()
    result = SMCEngine(config).run(bars)

    print_event_log(bars, result)
    save_chart(bars, result, args.chart_out)


if __name__ == "__main__":
    main()
