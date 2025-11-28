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

/**
 * Calculate Simple Moving Average (helper for EMA initialization)
 */
function calculateSMA(closes: number[], period: number, startIndex: number): number {
  let sum = 0;
  for (let i = startIndex - period + 1; i <= startIndex; i++) {
    sum += closes[i];
  }
  return sum / period;
}

/**
 * Calculate Exponential Moving Average (EMA)
 * Formula: EMA = alpha * x + (1 - alpha) * EMA[1]
 * where alpha = 2 / (length + 1)
 * First value uses SMA(src, length)
 */
function calculateEMA(candles: Candle[], period: number): Array<{ time: Time; value: number }> {
  if (candles.length < period) {
    return [];
  }

  const emaData: Array<{ time: Time; value: number }> = [];
  const closes = candles.map(c => c.close);
  const alpha = 2 / (period + 1);
  
  // First EMA value is SMA
  let ema = calculateSMA(closes, period, period - 1);
  emaData.push({
    time: (new Date(candles[period - 1].timestamp).getTime() / 1000) as Time,
    value: ema,
  });

  // Calculate subsequent EMA values
  for (let i = period; i < closes.length; i++) {
    ema = alpha * closes[i] + (1 - alpha) * ema;
    emaData.push({
      time: (new Date(candles[i].timestamp).getTime() / 1000) as Time,
      value: ema,
    });
  }

  return emaData;
}

/**
 * Calculate ZigZag points
 * Based on Pine Script ZigZag algorithm
 */
interface ZigZagPoint {
  time: Time;
  price: number;
  isHigh: boolean;
}

function calculateZigZag(
  candles: Candle[],
  depth: number = 12,
  deviation: number = 5,
  backstep: number = 2
): ZigZagPoint[] {
  if (candles.length < depth + backstep) {
    return [];
  }

  const points: ZigZagPoint[] = [];
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  const mintick = 0.01; // Minimum price movement (adjust based on your data)

  // Find swing points
  for (let i = depth; i < candles.length - backstep; i++) {
    // Find highest bar in the depth range
    let highestIdx = i - depth;
    for (let j = i - depth + 1; j <= i; j++) {
      if (highs[j] > highs[highestIdx]) {
        highestIdx = j;
      }
    }

    // Find lowest bar in the depth range
    let lowestIdx = i - depth;
    for (let j = i - depth + 1; j <= i; j++) {
      if (lows[j] < lows[lowestIdx]) {
        lowestIdx = j;
      }
    }

    // Check if high meets deviation requirement
    const highDeviation = highs[highestIdx] - highs[i - depth];
    if (highDeviation > deviation * mintick && highestIdx === i) {
      points.push({
        time: (new Date(candles[highestIdx].timestamp).getTime() / 1000) as Time,
        price: highs[highestIdx],
        isHigh: true,
      });
    }

    // Check if low meets deviation requirement
    const lowDeviation = lows[i - depth] - lows[lowestIdx];
    if (lowDeviation > deviation * mintick && lowestIdx === i) {
      points.push({
        time: (new Date(candles[lowestIdx].timestamp).getTime() / 1000) as Time,
        price: lows[lowestIdx],
        isHigh: false,
      });
    }
  }

  // Filter points to alternate between highs and lows
  const filteredPoints: ZigZagPoint[] = [];
  let lastWasHigh: boolean | null = null;

  for (const point of points) {
    if (lastWasHigh === null) {
      filteredPoints.push(point);
      lastWasHigh = point.isHigh;
    } else if (point.isHigh !== lastWasHigh) {
      filteredPoints.push(point);
      lastWasHigh = point.isHigh;
    } else {
      // Replace the last point if this one is more extreme
      const lastPoint = filteredPoints[filteredPoints.length - 1];
      if (point.isHigh && point.price > lastPoint.price) {
        filteredPoints[filteredPoints.length - 1] = point;
      } else if (!point.isHigh && point.price < lastPoint.price) {
        filteredPoints[filteredPoints.length - 1] = point;
      }
    }
  }

  return filteredPoints;
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
  const emaSeriesRefs = useRef<Map<number, ISeriesApi<"Line">>>(new Map());

  useEffect(() => {
    // Cleanup function that will run on unmount or when dependencies change
    const cleanup = () => {
      // Cleanup single series
      if (seriesRef.current && chart) {
        try {
          chart.removeSeries(seriesRef.current);
        } catch (e) {
          // Series might already be removed
        }
        seriesRef.current = null;
      }
      // Cleanup EMA series
      if (chart) {
        emaSeriesRefs.current.forEach((series) => {
          try {
            chart.removeSeries(series);
          } catch (e) {
            // Series might already be removed
          }
        });
      }
      emaSeriesRefs.current.clear();
    };

    if (!chart || !pane || !indicator.visible) {
      cleanup();
      return cleanup;
    }

    const filteredCandles = candles
      .filter((c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    // Handle EMA with multiple periods
    if (indicator.type === "EMA") {
      const periods = indicator.settings.periods || [20, 50, 100, 200];
      const colors = indicator.settings.colors || ["#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444"]; // Blue, Amber, Purple, Red
      
      // Remove old EMA series that are no longer needed
      const currentPeriods = new Set(periods);
      emaSeriesRefs.current.forEach((series, period) => {
        if (!currentPeriods.has(period)) {
          try {
            chart.removeSeries(series);
          } catch (e) {
            // Series might already be removed
          }
          emaSeriesRefs.current.delete(period);
        }
      });

      // Create/update EMA series for each period
      periods.forEach((period: number, index: number) => {
        if (filteredCandles.length < period) {
          // Not enough data, remove series if it exists
          const existingSeries = emaSeriesRefs.current.get(period);
          if (existingSeries) {
            try {
              chart.removeSeries(existingSeries);
            } catch (e) {
              // Series might already be removed
            }
            emaSeriesRefs.current.delete(period);
          }
          return;
        }

        const emaData = calculateEMA(filteredCandles, period);
        if (emaData.length === 0) return;

        let series = emaSeriesRefs.current.get(period);
        
        if (!series) {
          // Create new series
          try {
            series = pane.addSeries(LineSeries, {
              color: colors[index] || colors[0],
              lineWidth: indicator.settings.lineWidth || 1,
              title: `EMA(${period})`,
            });
            emaSeriesRefs.current.set(period, series);
          } catch (error) {
            console.warn(`DynamicIndicator: Error creating EMA(${period}) series`, error);
            return;
          }
        }

        // Update series data
        try {
          series.setData(emaData as LineData[]);
        } catch (error) {
          console.warn(`DynamicIndicator: Error setting EMA(${period}) data`, error);
        }
      });

      // Set pane height if specified
      if (indicator.settings.paneHeight !== undefined) {
        try {
          pane.setStretchFactor(indicator.settings.paneHeight);
        } catch (error) {
          console.warn(`DynamicIndicator: Error setting pane height for EMA`, error);
        }
      }

      // Return cleanup function for EMA
      return () => {
        emaSeriesRefs.current.forEach((series) => {
          try {
            chart?.removeSeries(series);
          } catch (e) {
            // Series might already be removed
          }
        });
        emaSeriesRefs.current.clear();
      };
    }

    // Handle ZigZag indicator
    if (indicator.type === "ZigZag") {
      const depth = indicator.settings.depth || 12;
      const deviation = indicator.settings.deviation || 5;
      const backstep = indicator.settings.backstep || 2;
      const lineWidth = indicator.settings.lineWidth || 2;
      const upColor = indicator.settings.upColor || "#00e677";
      const downColor = indicator.settings.downColor || "#ff5252";

      if (filteredCandles.length < depth + backstep) {
        return;
      }

      const zigzagPoints = calculateZigZag(filteredCandles, depth, deviation, backstep);
      
      if (zigzagPoints.length < 2) {
        return;
      }

      // Remove existing ZigZag series
      if (seriesRef.current) {
        try {
          chart.removeSeries(seriesRef.current);
        } catch (e) {
          // Series might already be removed
        }
        seriesRef.current = null;
      }

      // Create line data connecting consecutive ZigZag points
      const lineData: LineData[] = [];
      for (let i = 0; i < zigzagPoints.length; i++) {
        lineData.push({
          time: zigzagPoints[i].time,
          value: zigzagPoints[i].price,
        });
      }

      try {
        // Create series for ZigZag lines
        const zigzagSeries = pane.addSeries(LineSeries, {
          color: upColor, // Will alternate colors based on direction
          lineWidth: lineWidth as any,
          title: "ZigZag",
          priceLineVisible: false,
          lastValueVisible: false,
        });

        zigzagSeries.setData(lineData);
        seriesRef.current = zigzagSeries;

        // Set pane height if specified
        if (indicator.settings.paneHeight !== undefined) {
          try {
            pane.setStretchFactor(indicator.settings.paneHeight);
          } catch (error) {
            console.warn(`DynamicIndicator: Error setting pane height for ZigZag`, error);
          }
        }
      } catch (error) {
        console.warn(`DynamicIndicator: Error creating ZigZag series`, error);
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
    }

    // Handle other indicator types (RSI, MA, etc.)
    let indicatorData: Array<{ time: Time; value: number }> = [];

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

      // Set pane height if specified in settings
      if (indicator.settings.paneHeight !== undefined) {
        try {
          pane.setStretchFactor(indicator.settings.paneHeight);
        } catch (error) {
          console.warn(`DynamicIndicator: Error setting pane height for ${indicator.type}`, error);
        }
      }

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

