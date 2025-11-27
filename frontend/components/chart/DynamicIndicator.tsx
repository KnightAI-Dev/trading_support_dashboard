"use client";

import { useEffect, useRef } from "react";
import {
  IChartApi,
  IPaneApi,
  ISeriesApi,
  LineData,
  LineSeries,
  Time,
} from "lightweight-charts";
import { Candle } from "@/lib/api";
import { IndicatorConfig } from "@/lib/types";

interface DynamicIndicatorProps {
  chart: IChartApi | null;
  pane: IPaneApi<Time> | null;
  candles: Candle[];
  selectedSymbol: string;
  selectedTimeframe: string;
  indicator: IndicatorConfig;
}

/**
 * Calculate RSI (Relative Strength Index) from candle data
 */
function calculateRSI(candles: Candle[], period: number = 14): Array<{ time: Time; value: number }> {
  if (candles.length < period + 1) {
    return [];
  }

  const rsiData: Array<{ time: Time; value: number }> = [];
  const closes = candles.map(c => c.close);
  
  const changes: number[] = [];
  for (let i = 1; i < closes.length; i++) {
    changes.push(closes[i] - closes[i - 1]);
  }

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

  if (avgLoss !== 0) {
    const rs = avgGain / avgLoss;
    const rsi = 100 - (100 / (1 + rs));
    rsiData.push({
      time: (new Date(candles[period].timestamp).getTime() / 1000) as Time,
      value: rsi,
    });
  }

  for (let i = period; i < changes.length; i++) {
    const change = changes[i];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;

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

/**
 * Calculate Simple Moving Average
 */
function calculateMA(candles: Candle[], period: number): Array<{ time: Time; value: number }> {
  if (candles.length < period) {
    return [];
  }

  const maData: Array<{ time: Time; value: number }> = [];
  const closes = candles.map(c => c.close);

  for (let i = period - 1; i < closes.length; i++) {
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) {
      sum += closes[j];
    }
    const ma = sum / period;
    
    maData.push({
      time: (new Date(candles[i].timestamp).getTime() / 1000) as Time,
      value: ma,
    });
  }

  return maData;
}

export function DynamicIndicator({
  chart,
  pane,
  candles,
  selectedSymbol,
  selectedTimeframe,
  indicator,
}: DynamicIndicatorProps) {
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!chart || !pane || !indicator.visible) {
      if (seriesRef.current) {
        try {
          chart?.removeSeries(seriesRef.current);
        } catch (e) {
          // Series might already be removed
        }
        seriesRef.current = null;
      }
      return;
    }

    const filteredCandles = candles
      .filter((c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    let indicatorData: Array<{ time: Time; value: number }> = [];

    // Calculate indicator data based on type
    switch (indicator.type) {
      case "RSI":
        if (filteredCandles.length < (indicator.settings.period || 14) + 1) {
          return;
        }
        indicatorData = calculateRSI(filteredCandles, indicator.settings.period || 14);
        break;
      case "MA":
        if (filteredCandles.length < (indicator.settings.period || 20)) {
          return;
        }
        indicatorData = calculateMA(filteredCandles, indicator.settings.period || 20);
        break;
      default:
        // Other indicators not yet implemented
        return;
    }

    if (indicatorData.length === 0) {
      if (seriesRef.current) {
        try {
          chart.removeSeries(seriesRef.current);
        } catch (e) {
          // Series might already be removed
        }
        seriesRef.current = null;
      }
      return;
    }

    try {
      // Remove existing series if it exists
      if (seriesRef.current) {
        try {
          chart.removeSeries(seriesRef.current);
        } catch (e) {
          // Series might already be removed
        }
      }

      // Create new series on the provided pane
      const series = pane.addSeries(LineSeries, {
        color: indicator.settings.color || "#8b5cf6",
        lineWidth: indicator.settings.lineWidth || 2,
        title: indicator.name,
      });

      // Configure price scale for RSI (0-100 range)
      if (indicator.type === "RSI") {
        series.priceScale().applyOptions({
          scaleMargins: {
            top: 0.2,
            bottom: 0.05,
          },
        });

        // Add overbought/oversold lines
        series.createPriceLine({
          price: 70,
          color: "#ef4444",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "Overbought",
        });

        series.createPriceLine({
          price: 30,
          color: "#10b981",
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "Oversold",
        });
      }

      // Set indicator data
      series.setData(indicatorData as LineData[]);
      seriesRef.current = series;
    } catch (error) {
      console.warn(`DynamicIndicator: Error creating ${indicator.type} series`, error);
    }

    return () => {
      if (seriesRef.current && chart) {
        try {
          chart.removeSeries(seriesRef.current);
        } catch (e) {
          // Series might already be removed or chart disposed
        }
        seriesRef.current = null;
      }
    };
  }, [chart, pane, candles, selectedSymbol, selectedTimeframe, indicator]);

  return null;
}

