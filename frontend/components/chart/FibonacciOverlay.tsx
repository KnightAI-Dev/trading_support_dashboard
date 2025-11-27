"use client";

import { useEffect, useRef } from "react";
import {
  IChartApi,
  ISeriesApi,
  LineSeries,
  LineStyle,
  Time,
} from "lightweight-charts";
import { TradingSignal, SwingPoint } from "@/lib/api";

interface FibonacciOverlayProps {
  chart: IChartApi | null;
  signal: TradingSignal;
  swings: SwingPoint[];
}

export function FibonacciOverlay({
  chart,
  signal,
  swings,
}: FibonacciOverlayProps) {
  const seriesRef = useRef<ISeriesApi<"Line">[]>([]);

  useEffect(() => {
    if (!chart || !signal.swing_high || !signal.swing_low) return;

    // Cleanup previous series
    seriesRef.current.forEach((series) => {
      try {
        chart.removeSeries(series);
      } catch (e) {
        // Series might already be removed
      }
    });
    seriesRef.current = [];

    const high = signal.swing_high;
    const low = signal.swing_low;
    const range = high - low;

    // Fibonacci levels
    const fibLevels = [
      { name: "0%", value: high },
      { name: "23.6%", value: high - range * 0.236 },
      { name: "38.2%", value: high - range * 0.382 },
      { name: "50%", value: high - range * 0.5 },
      { name: "61.8%", value: high - range * 0.618 },
      { name: "78.6%", value: high - range * 0.786 },
      { name: "100%", value: low },
    ];

    // Find time range from swings
    const highSwing = swings.find((s) => Math.abs(s.price - high) < (high * 0.01));
    const lowSwing = swings.find((s) => Math.abs(s.price - low) < (low * 0.01));
    
    if (!highSwing || !lowSwing) return;

    const startTime = (new Date(Math.min(
      new Date(highSwing.timestamp).getTime(),
      new Date(lowSwing.timestamp).getTime()
    )).getTime() / 1000) as Time;

    const endTime = (new Date(Math.max(
      new Date(highSwing.timestamp).getTime(),
      new Date(lowSwing.timestamp).getTime()
    )).getTime() / 1000) as Time;

    // Create line series for Fibonacci levels
    fibLevels.forEach((level, index) => {
      const data = [
        { time: startTime, value: level.value },
        { time: endTime, value: level.value },
      ];
      
      let series: ISeriesApi<"Line">;
      if (index === 0 || index === fibLevels.length - 1) {
        // First and last level - solid line
        series = chart.addSeries(LineSeries, {
          color: "#ef4444",
          lineWidth: 2,
        });
      } else {
        // Middle levels - dashed
        series = chart.addSeries(LineSeries, {
          color: "#10b981",
          lineWidth: 1,
          lineStyle: LineStyle.Dashed,
        });
      }
      
      series.setData(data);
      seriesRef.current.push(series);
    });

    return () => {
      // Cleanup series on unmount
      seriesRef.current.forEach((series) => {
        try {
          chart.removeSeries(series);
        } catch (e) {
          // Series might already be removed
        }
      });
      seriesRef.current = [];
    };
  }, [chart, signal, swings]);

  return null;
}

