"use client";

import { useEffect, useRef } from "react";
import {
  IChartApi,
  ISeriesApi,
  LineSeries,
  LineStyle,
  Time,
} from "lightweight-charts";
import { SRLevel } from "@/lib/api";

interface SupportResistanceLinesProps {
  chart: IChartApi | null;
  series: ISeriesApi<"Candlestick"> | null;
  srLevels: SRLevel[];
}

export function SupportResistanceLines({
  chart,
  series,
  srLevels,
}: SupportResistanceLinesProps) {
  const seriesRef = useRef<ISeriesApi<"Line">[]>([]);

  useEffect(() => {
    if (!chart || !series || !srLevels.length) return;

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

    srLevels.forEach((level) => {
      const color = level.type === "support" ? "#10b981" : "#ef4444";
      const opacity = Math.min(level.strength / 10, 1);
      
      const lineSeries = chart.addSeries(LineSeries, {
        color: `${color}${Math.floor(opacity * 255).toString(16).padStart(2, '0')}`,
        lineWidth: level.type === "support" ? 2 : 1,
        lineStyle: level.touches >= 3 ? LineStyle.Solid : LineStyle.LargeDashed,
      });

      lineSeries.setData([
        { time: visibleRange.from as Time, value: level.level },
        { time: visibleRange.to as Time, value: level.level },
      ]);
      
      seriesRef.current.push(lineSeries);
    });

    return () => {
      // Cleanup series on unmount
      seriesRef.current.forEach((lineSeries) => {
        try {
          chart.removeSeries(lineSeries);
        } catch (e) {
          // Series might already be removed
        }
      });
      seriesRef.current = [];
    };
  }, [chart, series, srLevels]);

  return null;
}

