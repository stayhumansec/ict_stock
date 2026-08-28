"""Loads synthetic bars, runs SMCEngine, prints a human-checkable event log,
and saves a simple price+event chart.

Usage: python -m backtest.run_backtest
"""

from __future__ import annotations

import argparse
from typing import List

from backend.smc.config import SMCConfig
from backend.smc.engine import SMCEngine
from backend.smc.models import Bar, EngineResult, MitigationState
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


_UP_COLOR = "#26a69a"
_DOWN_COLOR = "#ef5350"
_BG_COLOR = "#131722"
_GRID_COLOR = "#2a2e39"
_TEXT_COLOR = "#d1d4dc"
_BULLISH_LINE_COLOR = "#26a69a"
_BEARISH_LINE_COLOR = "#ef5350"
_OB_BULLISH_COLOR = "#1e88e5"
_OB_BEARISH_COLOR = "#7e57c2"
_EQ_COLOR = "#ef5350"


def _draw_candles(ax, bars: List[Bar], start: int, rectangle_cls) -> None:
    for i, bar in enumerate(bars):
        x = start + i
        up = bar.close >= bar.open
        color = _UP_COLOR if up else _DOWN_COLOR
        ax.vlines(x, bar.low, bar.high, color=color, linewidth=1, zorder=2)
        body_bottom = min(bar.open, bar.close)
        body_height = max(abs(bar.close - bar.open), (bar.high - bar.low) * 0.01)
        ax.add_patch(
            rectangle_cls((x - 0.3, body_bottom), 0.6, body_height, facecolor=color, edgecolor=color, zorder=3)
        )


def _event_label_and_color(event_type_value: str, direction_value: str):
    label = {
        "BOS": "BOS",
        "CHOCH": "CHoCH",
        "CHOCH_FAILED": "CHoCH (failed)",
        "MSS": "MSS",
        "MSS_FAILED": "MSS (failed)",
    }.get(event_type_value, event_type_value)
    color = _BULLISH_LINE_COLOR if direction_value == "BULLISH" else _BEARISH_LINE_COLOR
    return label, color


def save_chart(bars: List[Bar], result: EngineResult, out_path: str, last_n_bars: int = 120) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
    except ImportError:
        print("\n[chart] matplotlib not installed — skipping chart, event log above is authoritative.")
        return

    n = len(bars)
    window_start = max(0, n - last_n_bars)
    window_bars = bars[window_start:]
    window_end = n - 1

    fig, ax = plt.subplots(figsize=(16, 8))
    fig.patch.set_facecolor(_BG_COLOR)
    ax.set_facecolor(_BG_COLOR)

    _draw_candles(ax, window_bars, window_start, Rectangle)

    y_range = max(b.high for b in window_bars) - min(b.low for b in window_bars)
    label_nudge = y_range * 0.018
    placed_labels: List[tuple] = []  # (x, y) already used, to nudge collisions

    def place_label(x: float, y: float, text: str, color: str, va: str) -> None:
        adj_y = y
        for px, py in placed_labels:
            if abs(x - px) < len(window_bars) * 0.05 and abs(adj_y - py) < label_nudge * 1.5:
                adj_y = py + label_nudge if va == "bottom" else py - label_nudge
        placed_labels.append((x, adj_y))
        ax.text(x, adj_y, f" {text}", color=color, fontsize=8, va=va, zorder=6)

    # --- Structure events: dashed labeled line from the reference bar to
    # the confirming bar, extended a few bars for readability. ---
    for e in sorted(result.structure_events, key=lambda e: e.confirmed_index):
        if e.confirmed_index < window_start:
            continue
        label, color = _event_label_and_color(e.event_type.value, e.direction.value)
        line_start = max(window_start, e.confirmed_index - 8)
        line_end = min(window_end, e.confirmed_index + 4)
        ax.hlines(e.reference_price, line_start, line_end, colors=color, linestyles="dashed", linewidth=1.1, zorder=4)
        va = "bottom" if e.direction.value == "BULLISH" else "top"
        place_label(line_start, e.reference_price, label, color, va)

    # --- Equal highs / equal lows pools: dotted labeled line across their
    # member bars. ---
    for pool in result.liquidity_pools:
        if pool.pool_type.value not in ("EQUAL_HIGHS", "EQUAL_LOWS"):
            continue
        if not pool.member_indices or max(pool.member_indices) < window_start:
            continue
        label = "EQH" if pool.pool_type.value == "EQUAL_HIGHS" else "EQL"
        line_start = max(window_start, min(pool.member_indices))
        line_end = min(window_end, pool.formed_index + 3)
        ax.hlines(pool.price, line_start, line_end, colors=_EQ_COLOR, linestyles="dotted", linewidth=1.1, zorder=4)
        place_label(line_start, pool.price, label, _EQ_COLOR, "bottom")

    # --- Order block / breaker zones: shaded rectangle bounded to the
    # zone's own price range (never full chart height) from formation to
    # last update (or a short default span if still open). Invalidated
    # OBs are skipped - they are no longer live reference levels. ---
    for z in result.zones:
        if "ORDER_BLOCK" not in z.kind.value and "BREAKER" not in z.kind.value:
            continue
        if z.confirmed_index < window_start:
            continue
        if z.state == MitigationState.INVALIDATED:
            continue
        zone_end = z.last_updated_index if z.last_updated_index is not None else min(window_end, z.confirmed_index + 15)
        zone_start = max(window_start, z.formed_index)
        color = _OB_BULLISH_COLOR if "BULLISH" in z.kind.value else _OB_BEARISH_COLOR
        ax.add_patch(
            Rectangle(
                (zone_start, z.bottom),
                max(zone_end - zone_start, 0.5),
                z.top - z.bottom,
                facecolor=color,
                edgecolor=color,
                alpha=0.18,
                linewidth=0.8,
                zorder=1,
            )
        )

    # --- Liquidity sweeps: small marker at the swept price. ---
    for sw in result.liquidity_sweeps:
        if sw.swept_index < window_start:
            continue
        marker_color = "#ab47bc"
        ax.scatter(sw.swept_index, sw.swept_price, color=marker_color, marker="v", s=18, alpha=0.7, zorder=5)

    # X-axis: show HH:MM at evenly spaced ticks.
    tick_step = max(1, len(window_bars) // 8)
    tick_positions = list(range(window_start, n, tick_step))
    tick_labels = [f"{bars[i].timestamp:%H:%M}" for i in tick_positions]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, color=_TEXT_COLOR)

    ax.set_xlim(window_start - 1, window_end + 1)
    ax.tick_params(axis="y", colors=_TEXT_COLOR)
    ax.grid(color=_GRID_COLOR, linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_color(_GRID_COLOR)

    last_close = window_bars[-1].close
    ax.set_title(
        f"SMC Engine — synthetic NIFTY 5m (last {len(window_bars)} bars, close {last_close:.2f})",
        color=_TEXT_COLOR,
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=140, facecolor=_BG_COLOR)
    print(f"\n[chart] saved to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SMC engine against generated synthetic data.")
    parser.add_argument("--n-bars", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--chart-out", type=str, default="backtest/output_chart.png")
    parser.add_argument("--last-n-bars", type=int, default=120, help="how many trailing bars to render on the chart")
    args = parser.parse_args()

    bars = generate_synthetic_bars(seed=args.seed, n_bars=args.n_bars)
    config = SMCConfig()
    result = SMCEngine(config).run(bars)

    print_event_log(bars, result)
    save_chart(bars, result, args.chart_out, last_n_bars=args.last_n_bars)


if __name__ == "__main__":
    main()
