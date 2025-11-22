"use client";

import { useEffect, useRef } from "react";
import { IChartApi, ISeriesApi, Time } from "lightweight-charts";
import { TradingSignal } from "@/lib/api";

interface EntrySlTpLinesProps {
  chart: IChartApi | null;
  series: ISeriesApi<"Candlestick"> | null;
  signal: TradingSignal;
}

export function EntrySlTpLines({
  chart,
  series,
  signal,
}: EntrySlTpLinesProps) {
  const seriesRef = useRef<ISeriesApi<"Line">[]>([]);

  useEffect(() => {
    if (!chart || !series || !signal) return;

    try {
      // Check if chart is still valid (not disposed)
      if (!chart.timeScale || !chart.addLineSeries) return;

      // Cleanup previous series
      seriesRef.current.forEach((lineSeries) => {
        try {
          chart.removeSeries(lineSeries);
        } catch (e) {
          // Series might already be removed
        }
      });
      seriesRef.current = [];

      const timeScale = chart.timeScale();
      const visibleRange = timeScale.getVisibleRange();
      
      if (!visibleRange) return;

    const now = (Date.now() / 1000) as Time;
    const future = (visibleRange.to as number + 86400) as Time; // 24 hours ahead

    // Entry line
    if (signal.entry1) {
      const entrySeries = chart.addLineSeries({
        color: "#3b82f6",
        lineWidth: 2,
        lineStyle: 1, // Dotted
      });
      entrySeries.setData([
        { time: visibleRange.from as Time, value: signal.entry1 },
        { time: future, value: signal.entry1 },
      ]);
      seriesRef.current.push(entrySeries);
    }

    // Stop Loss
    if (signal.sl) {
      const slSeries = chart.addLineSeries({
        color: "#ef4444",
        lineWidth: 2,
        lineStyle: 2, // Dashed
      });
      slSeries.setData([
        { time: visibleRange.from as Time, value: signal.sl },
        { time: future, value: signal.sl },
      ]);
      seriesRef.current.push(slSeries);
    }

    // Take Profit levels
    if (signal.tp1) {
      const tp1Series = chart.addLineSeries({
        color: "#10b981",
        lineWidth: 2,
        lineStyle: 1,
      });
      tp1Series.setData([
        { time: visibleRange.from as Time, value: signal.tp1 },
        { time: future, value: signal.tp1 },
      ]);
      seriesRef.current.push(tp1Series);
    }

    if (signal.tp2) {
      const tp2Series = chart.addLineSeries({
        color: "#10b981",
        lineWidth: 1.5,
        lineStyle: 2,
      });
      tp2Series.setData([
        { time: visibleRange.from as Time, value: signal.tp2 },
        { time: future, value: signal.tp2 },
      ]);
      seriesRef.current.push(tp2Series);
    }

    if (signal.tp3) {
      const tp3Series = chart.addLineSeries({
        color: "#10b981",
        lineWidth: 1,
        lineStyle: 2,
      });
      tp3Series.setData([
        { time: visibleRange.from as Time, value: signal.tp3 },
        { time: future, value: signal.tp3 },
      ]);
      seriesRef.current.push(tp3Series);
    }
    } catch (error) {
      // Chart might be disposed, ignore the error
      console.warn("EntrySlTpLines: Chart is disposed", error);
      return;
    }

    return () => {
      // Cleanup series on unmount
      try {
        if (chart && chart.removeSeries) {
          seriesRef.current.forEach((lineSeries) => {
            try {
              chart.removeSeries(lineSeries);
            } catch (e) {
              // Series might already be removed
            }
          });
        }
      } catch (error) {
        // Chart might be disposed, ignore
      }
      seriesRef.current = [];
    };
  }, [chart, series, signal]);

  return null;
}

