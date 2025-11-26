"use client";

import { useEffect, useRef } from "react";
import { IChartApi, ISeriesApi, Time, LineData } from "lightweight-charts";
import { Candle } from "@/lib/api";

interface MovingAveragesProps {
  chart: IChartApi | null;
  candles: Candle[];
  selectedSymbol: string;
  selectedTimeframe: string;
  showMA7?: boolean;
  showMA25?: boolean;
  showMA99?: boolean;
}

/**
 * Calculate Simple Moving Average (SMA) from candle data
 * @param candles Array of candles sorted by timestamp
 * @param period Moving average period
 * @returns Array of MA values with timestamps
 */
function calculateMA(candles: Candle[], period: number): Array<{ time: Time; value: number }> {
  if (candles.length < period) {
    return [];
  }

  const maData: Array<{ time: Time; value: number }> = [];
  const closes = candles.map(c => c.close);

  // Calculate SMA for each period
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

export function MovingAverages({
  chart,
  candles,
  selectedSymbol,
  selectedTimeframe,
  showMA7 = true,
  showMA25 = true,
  showMA99 = true,
}: MovingAveragesProps) {
  const ma7SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma25SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ma99SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  useEffect(() => {
    if (!chart) return;

    // Filter candles for current symbol and timeframe
    const filteredCandles = candles
      .filter((c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    try {
      // Check if chart is still valid
      if (!chart.addLineSeries) return;

      // Remove existing MA series if they exist
      [ma7SeriesRef.current, ma25SeriesRef.current, ma99SeriesRef.current].forEach((series) => {
        if (series) {
          try {
            chart.removeSeries(series);
          } catch (e) {
            // Series might already be removed
          }
        }
      });

      ma7SeriesRef.current = null;
      ma25SeriesRef.current = null;
      ma99SeriesRef.current = null;

      // Calculate and add MA(7)
      if (showMA7 && filteredCandles.length >= 7) {
        const ma7Data = calculateMA(filteredCandles, 7);
        if (ma7Data.length > 0) {
          const ma7Series = chart.addLineSeries({
            color: "#3b82f6", // Blue
            lineWidth: 1,
            title: "MA(7)",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          ma7Series.setData(ma7Data as LineData[]);
          ma7SeriesRef.current = ma7Series;
        }
      }

      // Calculate and add MA(25)
      if (showMA25 && filteredCandles.length >= 25) {
        const ma25Data = calculateMA(filteredCandles, 25);
        if (ma25Data.length > 0) {
          const ma25Series = chart.addLineSeries({
            color: "#f59e0b", // Amber/Orange
            lineWidth: 1,
            title: "MA(25)",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          ma25Series.setData(ma25Data as LineData[]);
          ma25SeriesRef.current = ma25Series;
        }
      }

      // Calculate and add MA(99)
      if (showMA99 && filteredCandles.length >= 99) {
        const ma99Data = calculateMA(filteredCandles, 99);
        if (ma99Data.length > 0) {
          const ma99Series = chart.addLineSeries({
            color: "#8b5cf6", // Purple
            lineWidth: 1,
            title: "MA(99)",
            priceLineVisible: false,
            lastValueVisible: true,
          });
          ma99Series.setData(ma99Data as LineData[]);
          ma99SeriesRef.current = ma99Series;
        }
      }
    } catch (error) {
      console.warn("MovingAverages: Error creating MA series", error);
    }

    return () => {
      if (chart) {
        [ma7SeriesRef.current, ma25SeriesRef.current, ma99SeriesRef.current].forEach((series) => {
          if (series) {
            try {
              chart.removeSeries(series);
            } catch (e) {
              // Series might already be removed or chart disposed
            }
          }
        });
        ma7SeriesRef.current = null;
        ma25SeriesRef.current = null;
        ma99SeriesRef.current = null;
      }
    };
  }, [chart, candles, selectedSymbol, selectedTimeframe, showMA7, showMA25, showMA99]);

  return null; // This component doesn't render anything
}

