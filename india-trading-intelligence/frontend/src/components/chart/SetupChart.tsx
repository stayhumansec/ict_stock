"use client";

import { useEffect, useRef } from "react";
import { CandlestickSeries, LineStyle, createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import type { Signal } from "@/lib/types";
import { generateMockBars } from "@/lib/mock-ohlc";

interface PriceLineSpec {
  price: number;
  color: string;
  title: string;
  style?: LineStyle;
}

function buildPriceLines(signal: Signal): PriceLineSpec[] {
  const lines: PriceLineSpec[] = [];

  if (signal.entry !== null) {
    lines.push({ price: signal.entry, color: "#38bdf8", title: "Entry", style: LineStyle.Solid });
  }
  if (signal.stopLoss !== null) {
    lines.push({ price: signal.stopLoss, color: "#f0475c", title: "Stop", style: LineStyle.Solid });
  }
  signal.targets.forEach((t, i) => {
    lines.push({ price: t, color: "#2fbf71", title: `Target ${i + 1}`, style: LineStyle.Dashed });
  });
  signal.coreSignal.forEach((ref) => {
    lines.push({ price: ref.price, color: "#eab308", title: ref.kind, style: LineStyle.Dotted });
  });
  signal.confirmations.forEach((ref) => {
    lines.push({ price: ref.price, color: "#3b82f6", title: ref.kind, style: LineStyle.Dotted });
  });
  signal.conflicts.forEach((ref) => {
    lines.push({ price: ref.price, color: "#a78bfa", title: ref.kind, style: LineStyle.Dotted });
  });

  return lines;
}

export function SetupChart({ signal }: { signal: Signal }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const styles = getComputedStyle(document.documentElement);
    const textColor = styles.getPropertyValue("--text-muted").trim() || "#8a93a3";
    const gridColor = styles.getPropertyValue("--border").trim() || "#232a37";
    const bgColor = styles.getPropertyValue("--surface").trim() || "#10141b";

    const chart = createChart(container, {
      width: container.clientWidth,
      height: 340,
      layout: { background: { color: bgColor }, textColor, fontFamily: "var(--font-inter)" },
      grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
      timeScale: { borderColor: gridColor, timeVisible: true },
      rightPriceScale: { borderColor: gridColor },
      crosshair: { mode: 0 },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#2fbf71",
      downColor: "#f0475c",
      borderVisible: false,
      wickUpColor: "#2fbf71",
      wickDownColor: "#f0475c",
    });

    const anchor = signal.entry ?? signal.stopLoss ?? signal.targets[0] ?? 100;
    const bars = generateMockBars(signal.id, anchor);
    series.setData(bars);

    for (const line of buildPriceLines(signal)) {
      series.createPriceLine({
        price: line.price,
        color: line.color,
        lineWidth: 1,
        lineStyle: line.style ?? LineStyle.Dotted,
        axisLabelVisible: true,
        title: line.title,
      });
    }

    chart.timeScale().fitContent();

    const handleResize = () => chart.applyOptions({ width: container.clientWidth });
    window.addEventListener("resize", handleResize);

    chartRef.current = chart;
    seriesRef.current = series;

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signal.id]);

  return (
    <div>
      <div ref={containerRef} className="w-full" />
      <p className="mt-2 text-[11px] text-text-faint">
        Illustrative candles — a real market-data feed is not wired into this chart yet. Dotted lines mark the
        structural references below; solid/dashed lines mark entry, stop, and targets.
      </p>
    </div>
  );
}
