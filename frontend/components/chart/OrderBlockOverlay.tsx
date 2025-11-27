"use client";

import { useEffect } from "react";
import {
  AreaSeries,
  IChartApi,
  ISeriesApi,
  LineSeries,
  Time,
} from "lightweight-charts";
import { TradingSignal, Candle } from "@/lib/api";

interface OrderBlockOverlayProps {
  chart: IChartApi | null;
  signal: TradingSignal;
  candles: Candle[];
}

export function OrderBlockOverlay({
  chart,
  signal,
  candles,
}: OrderBlockOverlayProps) {
  useEffect(() => {
    if (!chart || !signal.swing_high || !signal.swing_low || !candles.length) return;

    // Find order block candles (last bullish/bearish candle before swing)
    const sortedCandles = [...candles].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );

    // Find the swing point candle
    const swingPrice = signal.direction === "long" ? signal.swing_low : signal.swing_high;
    const swingCandleIndex = sortedCandles.findIndex(
      (c) => Math.abs(c.low - swingPrice) < (swingPrice * 0.01) || 
            Math.abs(c.high - swingPrice) < (swingPrice * 0.01)
    );

    if (swingCandleIndex < 1) return;

    // Get the candle before the swing (order block)
    const obCandle = sortedCandles[swingCandleIndex - 1];
    
    if (!obCandle) return;

    const obTime = (new Date(obCandle.timestamp).getTime() / 1000) as Time;
    const nextTime = swingCandleIndex < sortedCandles.length - 1
      ? (new Date(sortedCandles[swingCandleIndex + 1].timestamp).getTime() / 1000) as Time
      : (new Date(Date.now() / 1000).getTime()) as Time;

    const createdSeries: Array<ISeriesApi<"Area"> | ISeriesApi<"Line">> = [];

    // Create a box series (using area series as workaround)
    const boxSeries = chart.addSeries(AreaSeries, {
      lineColor: signal.direction === "long" ? "#10b981" : "#ef4444",
      topColor: signal.direction === "long" ? "#10b98140" : "#ef444440",
      bottomColor: signal.direction === "long" ? "#10b98110" : "#ef444410",
      lineWidth: 1,
    });
    createdSeries.push(boxSeries);

    const boxData = [
      { time: obTime, value: obCandle.high },
      { time: obTime, value: obCandle.low },
      { time: nextTime, value: obCandle.low },
      { time: nextTime, value: obCandle.high },
    ];

    // Draw box using line series for borders
    const topLine = chart.addSeries(LineSeries, {
      color: signal.direction === "long" ? "#10b981" : "#ef4444",
      lineWidth: 2,
    });
    topLine.setData([
      { time: obTime, value: obCandle.high },
      { time: nextTime, value: obCandle.high },
    ]);

    const bottomLine = chart.addSeries(LineSeries, {
      color: signal.direction === "long" ? "#10b981" : "#ef4444",
      lineWidth: 2,
    });
    bottomLine.setData([
      { time: obTime, value: obCandle.low },
      { time: nextTime, value: obCandle.low },
    ]);

    createdSeries.push(topLine, bottomLine);

    return () => {
      createdSeries.forEach((series) => {
        try {
          chart.removeSeries(series);
        } catch {
          // Series might already be removed
        }
      });
    };
  }, [chart, signal, candles]);

  return null;
}

