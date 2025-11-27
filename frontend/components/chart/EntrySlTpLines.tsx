"use client";

import { useEffect, useRef } from "react";
import {
  IChartApi,
  ISeriesApi,
  LineStyle,
  LineWidth,
  Time,
} from "lightweight-charts";
import { TradingSignal } from "@/lib/api";

interface EntrySlTpLinesProps {
  chart: IChartApi | null;
  series: ISeriesApi<"Candlestick"> | null;
  signal: TradingSignal;
}

const COLORS = {
  entry: "#2563eb",
  stopLoss: "#ef4444",
  takeProfit: "#10b981",
  swingHigh: "#ffffff",
  swingLow: "#ffffff",
};

const toEpochSeconds = (timestamp?: string | number | null): number | null => {
  if (timestamp == null) return null;

  const numericValue =
    typeof timestamp === "number" ? timestamp : Number(timestamp);
  if (!Number.isNaN(numericValue) && Number.isFinite(numericValue)) {
    return numericValue > 1e11
      ? Math.floor(numericValue / 1000)
      : Math.floor(numericValue);
  }

  if (typeof timestamp === "string") {
    const parsed = Date.parse(timestamp);
    if (!Number.isNaN(parsed)) {
      return Math.floor(parsed / 1000);
    }
  }

  return null;
};

export function EntrySlTpLines({
  chart,
  series,
  signal,
}: EntrySlTpLinesProps) {
  const seriesRef = useRef<ISeriesApi<"Line">[]>([]);

  useEffect(() => {
    if (!chart || !series || !signal) return;

    const cleanupSeries = () => {
      if (!chart?.removeSeries) {
        seriesRef.current = [];
        return;
      }

      seriesRef.current.forEach((lineSeries) => {
        try {
          chart.removeSeries(lineSeries);
        } catch {
          // Series might already be removed
        }
      });
      seriesRef.current = [];
    };

    try {
      if (!chart.timeScale || !chart.addLineSeries) return cleanupSeries();

      cleanupSeries();

      const timeScale = chart.timeScale();
      const visibleRange = timeScale.getVisibleRange();
      if (!visibleRange) return;

      const nowSec = Math.floor(Date.now() / 1000);
      const swingHighSeconds = toEpochSeconds(signal.swing_high_timestamp);
      const swingLowSeconds = toEpochSeconds(signal.swing_low_timestamp);
      const swingTimestamps = [swingHighSeconds, swingLowSeconds].filter(
        (value): value is number => typeof value === "number"
      );
      const fallbackFrom =
        typeof visibleRange.from === "number" ? visibleRange.from : nowSec - 86400;
      const fromTimestamp =
        swingTimestamps.length > 0
          ? Math.min(...swingTimestamps) // Oldest swing timestamp anchors our overlays
          : fallbackFrom;
      const toTimestamp =
        typeof visibleRange.to === "number" ? visibleRange.to : nowSec;

      const rangeStart = fromTimestamp as Time;
      const extendedRangeEnd = (toTimestamp + 86400) as Time;

      // Calculate swing line time range: from min to max of swing timestamps
      const swingTimeRange = swingTimestamps.length === 2
        ? {
            start: Math.min(swingHighSeconds!, swingLowSeconds!) as Time,
            end: Math.max(swingHighSeconds!, swingLowSeconds!) as Time,
          }
        : null;

      const addHorizontalLine = (
        value: number | null | undefined,
        {
          color,
          lineWidth = 1 as LineWidth,
          lineStyle = LineStyle.Solid,
          title,
          timeRange,
        }: {
          color: string;
          lineWidth?: LineWidth;
          lineStyle?: LineStyle;
          title: string;
          timeRange?: { start: Time; end: Time };
        }
      ) => {
        if (value == null) return;

        const lineSeries = chart.addLineSeries({
          color,
          lineWidth,
          lineStyle,
          title,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });

        // Use custom time range if provided, otherwise use default range
        const startTime = timeRange ? timeRange.start : rangeStart;
        const endTime = timeRange ? timeRange.end : extendedRangeEnd;

        lineSeries.setData([
          { time: startTime, value },
          { time: endTime, value },
        ]);

        seriesRef.current.push(lineSeries);
      };

      addHorizontalLine(signal.entry1, {
        color: COLORS.entry,
        lineWidth: 2,
        lineStyle: LineStyle.Solid,
        title: "Entry",
      });

      addHorizontalLine(signal.sl, {
        color: COLORS.stopLoss,
        lineWidth: 2,
        lineStyle: LineStyle.LargeDashed,
        title: "Stop Loss",
      });

      addHorizontalLine(signal.tp1, {
        color: COLORS.takeProfit,
        lineStyle: LineStyle.Solid,
        title: "TP 1",
      });
      addHorizontalLine(signal.tp2, {
        color: COLORS.takeProfit,
        lineStyle: LineStyle.Dashed,
        title: "TP 2",
      });
      addHorizontalLine(signal.tp3, {
        color: COLORS.takeProfit,
        lineStyle: LineStyle.Dotted,
        title: "TP 3",
      });

      // Swing high and low lines only between their timestamps
      if (swingTimeRange && signal.swing_high != null) {
        addHorizontalLine(signal.swing_high, {
          color: COLORS.swingHigh,
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          title: "Swing High",
          timeRange: swingTimeRange,
        });
      }

      if (swingTimeRange && signal.swing_low != null) {
        addHorizontalLine(signal.swing_low, {
          color: COLORS.swingLow,
          lineWidth: 2,
          lineStyle: LineStyle.Solid,
          title: "Swing Low",
          timeRange: swingTimeRange,
        });
      }
    } catch (error) {
      console.warn("EntrySlTpLines: Chart is disposed", error);
      cleanupSeries();
    }

    return cleanupSeries;
  }, [chart, series, signal]);

  return null;
}

