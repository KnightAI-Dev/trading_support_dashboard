"use client";

import { useEffect } from "react";
import { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import { SwingPoint } from "@/lib/api";
import { Candle } from "@/lib/api";

interface SwingMarkersProps {
  chart: IChartApi | null;
  series: ISeriesApi<"Candlestick"> | null;
  swings: SwingPoint[];
  candles: Candle[];
}

export function SwingMarkers({
  chart,
  series,
  swings,
  candles,
}: SwingMarkersProps) {
  useEffect(() => {
    if (!chart || !series || !swings.length || !candles.length) return;

    try {
      // Check if chart/series are still valid (not disposed)
      // Try to access a property that would throw if disposed
      if (!chart.timeScale || !series.setMarkers) return;

      const markers = swings
        .map((swing) => {
          const candle = candles.find(
            (c) => Math.abs(new Date(c.timestamp).getTime() - new Date(swing.timestamp).getTime()) < 60000
          );
          
          if (!candle) return null;

          return {
            time: (new Date(swing.timestamp).getTime() / 1000) as Time,
            position: swing.type === "high" ? ("aboveBar" as const) : ("belowBar" as const),
            color: swing.type === "high" ? "#10b981" : "#ef4444",
            shape: swing.type === "high" ? ("circle" as const) : ("circle" as const),
            size: 1.5,
            text: swing.type === "high" ? "SH" : "SL",
          };
        })
        .filter(Boolean)
        // Sort markers by time in ascending order (required by lightweight-charts)
        .sort((a, b) => {
          if (!a || !b) return 0;
          return (a.time as number) - (b.time as number);
        });

      series.setMarkers(markers as any);
    } catch (error) {
      // Chart or series might be disposed, ignore the error
      console.warn("SwingMarkers: Chart or series is disposed", error);
      return;
    }

    return () => {
      try {
        if (series && series.setMarkers) {
          series.setMarkers([]);
        }
      } catch (error) {
        // Series might be disposed, ignore
      }
    };
  }, [chart, series, swings, candles]);

  return null;
}

