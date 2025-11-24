"use client";

import { useEffect, useRef } from "react";
import { IChartApi, ISeriesApi, Time, LineData } from "lightweight-charts";
import { Candle } from "@/lib/api";

interface RSIIndicatorProps {
  chart: IChartApi | null;
  candles: Candle[];
  selectedSymbol: string;
  selectedTimeframe: string;
  period?: number;
  height?: number; // Height percentage (0-100) for RSI pane
}

/**
 * Calculate RSI (Relative Strength Index) from candle data
 * @param candles Array of candles sorted by timestamp
 * @param period RSI period (default: 14)
 * @returns Array of RSI values with timestamps
 */
function calculateRSI(candles: Candle[], period: number = 14): Array<{ time: Time; value: number }> {
  if (candles.length < period + 1) {
    return [];
  }

  const rsiData: Array<{ time: Time; value: number }> = [];
  const closes = candles.map(c => c.close);
  
  // Calculate price changes
  const changes: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    changes.push(closes[i] - closes[i - 1]);
  }

  // Calculate initial average gain and loss
  let avgGain = 0;
  let avgLoss = 0;
  
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) {
      avgGain += changes[i];
    } else {
      avgLoss += Math.abs(changes[i]);
    }
  }
  
  avgGain /= period;
  avgLoss /= period;

  // Calculate RSI for the first period
  if (avgLoss !== 0) {
    const rs = avgGain / avgLoss;
    const rsi = 100 - (100 / (1 + rs));
    rsiData.push({
      time: (new Date(candles[period].timestamp).getTime() / 1000) as Time,
      value: rsi,
    });
  }

  // Calculate RSI for remaining periods using Wilder's smoothing method
  for (let i = period; i < changes.length; i++) {
    const change = changes[i];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;

    // Wilder's smoothing: new average = (previous average * (period - 1) + current value) / period
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    if (avgLoss !== 0) {
      const rs = avgGain / avgLoss;
      const rsi = 100 - (100 / (1 + rs));
      rsiData.push({
        time: (new Date(candles[i + 1].timestamp).getTime() / 1000) as Time,
        value: rsi,
      });
    }
  }

  return rsiData;
}

export function RSIIndicator({
  chart,
  candles,
  selectedSymbol,
  selectedTimeframe,
  period = 14,
  height = 30,
}: RSIIndicatorProps) {
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!chart) return;

    // Filter candles for current symbol and timeframe
    const filteredCandles = candles
      .filter((c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    if (filteredCandles.length < period + 1) {
      // Not enough data for RSI calculation
      if (rsiSeriesRef.current) {
        try {
          chart.removeSeries(rsiSeriesRef.current);
        } catch (e) {
          // Series might already be removed
        }
        rsiSeriesRef.current = null;
      }
      return;
    }

    // Calculate RSI
    const rsiData = calculateRSI(filteredCandles, period);

    if (rsiData.length === 0) {
      if (rsiSeriesRef.current) {
        try {
          chart.removeSeries(rsiSeriesRef.current);
        } catch (e) {
          // Series might already be removed
        }
        rsiSeriesRef.current = null;
      }
      return;
    }

    try {
      // Check if chart is still valid
      if (!chart.addLineSeries) return;

      // Remove existing RSI series if it exists
      if (rsiSeriesRef.current) {
        try {
          chart.removeSeries(rsiSeriesRef.current);
        } catch (e) {
          // Series might already be removed
        }
      }

      // Create new RSI series
      const rsiSeries = chart.addLineSeries({
        color: "#8b5cf6", // Purple color for RSI
        lineWidth: 2,
        priceScaleId: "rsi", // Use separate price scale
        title: `RSI(${period})`,
      });

      // Configure RSI price scale (0-100 range) - position at bottom of chart
      // height is percentage of chart height (10-50%), convert to scale margins
      // If height is 30%, RSI takes bottom 30% of chart, so top margin = 70%
      const topMargin = (100 - height) / 100;
      rsiSeries.priceScale().applyOptions({
        scaleMargins: {
          top: Math.max(0.05, Math.min(0.9, topMargin)), // Clamp between 5% and 90%
          bottom: 0.05,
        },
        minimum: 0,
        maximum: 100,
      });

      // Set RSI data
      rsiSeries.setData(rsiData as LineData[]);

      // Add overbought (70) and oversold (30) reference lines
      rsiSeries.createPriceLine({
        price: 70,
        color: "#ef4444",
        lineWidth: 1,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: "Overbought",
      });

      rsiSeries.createPriceLine({
        price: 30,
        color: "#10b981",
        lineWidth: 1,
        lineStyle: 2, // Dashed
        axisLabelVisible: true,
        title: "Oversold",
      });

      rsiSeriesRef.current = rsiSeries;
    } catch (error) {
      console.warn("RSIIndicator: Error creating RSI series", error);
    }

    return () => {
      if (rsiSeriesRef.current && chart) {
        try {
          chart.removeSeries(rsiSeriesRef.current);
        } catch (e) {
          // Series might already be removed or chart disposed
        }
        rsiSeriesRef.current = null;
      }
    };
  }, [chart, candles, selectedSymbol, selectedTimeframe, period]);

  return null; // This component doesn't render anything
}

