"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  Time,
  CandlestickData,
  ColorType,
} from "lightweight-charts";
import { useMarketStore } from "@/stores/useMarketStore";
import { Candle, fetchCandles } from "@/lib/api";
import { SwingMarkers } from "./SwingMarkers";
import { FibonacciOverlay } from "./FibonacciOverlay";
import { OrderBlockOverlay } from "./OrderBlockOverlay";
import { SupportResistanceLines } from "./SupportResistanceLines";
import { EntrySlTpLines } from "./EntrySlTpLines";

interface ChartContainerProps {
  width?: number;
  height?: number;
}

export function ChartContainer({
  width,
  height = 600,
}: ChartContainerProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [containerWidth, setContainerWidth] = useState(width || 800);
  const [oldestLoadedTime, setOldestLoadedTime] = useState<number | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const loadMoreTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const {
    candles,
    selectedSymbol,
    selectedTimeframe,
    swingPoints,
    srLevels,
    latestSignal,
    chartSettings,
    setCandles,
  } = useMarketStore();

  // Initialize chart
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: containerWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#0a0e13" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        borderColor: "#374151",
      },
      timeScale: {
        borderColor: "#374151",
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        const newWidth = chartContainerRef.current.clientWidth;
        setContainerWidth(newWidth);
        chart.applyOptions({ width: newWidth });
      }
    };

    window.addEventListener("resize", handleResize);
    handleResize();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [height]);

  // Load more historical data when user scrolls back
  const loadMoreHistoricalData = useCallback(
    async (beforeTime: number) => {
      if (isLoadingMore || !selectedSymbol || !selectedTimeframe) return;

      // Check if we've already loaded data before this time
      if (oldestLoadedTime && beforeTime >= oldestLoadedTime) {
        return; // Already have data for this range
      }

      setIsLoadingMore(true);
      try {
        const beforeDate = new Date(beforeTime * 1000).toISOString();
        const newCandles = await fetchCandles(
          selectedSymbol,
          selectedTimeframe,
          500, // Load 500 more candles
          beforeDate
        );

        if (newCandles.length > 0) {
          // Get current candles from the store state
          const currentCandles = useMarketStore.getState().candles;
          
          // Separate candles for current symbol/timeframe and others
          const otherCandles = currentCandles.filter(
            (c) => !(c.symbol === selectedSymbol && c.timeframe === selectedTimeframe)
          );
          const filteredExisting = currentCandles.filter(
            (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
          );

          // Merge and deduplicate by timestamp for current symbol/timeframe
          const candleMap = new Map<string, Candle>();
          
          // Add existing candles for current symbol/timeframe
          filteredExisting.forEach((candle) => {
            candleMap.set(candle.timestamp, candle);
          });

          // Add new candles (they will overwrite if duplicate, but new ones should be older)
          newCandles.forEach((candle) => {
            if (!candleMap.has(candle.timestamp)) {
              candleMap.set(candle.timestamp, candle);
            }
          });

          // Convert back to array and sort by timestamp
          const mergedForSymbol = Array.from(candleMap.values()).sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          );

          // Combine with other candles and update store
          setCandles([...otherCandles, ...mergedForSymbol]);

          // Update oldest loaded time
          const oldest = Math.min(
            ...newCandles.map((c) => new Date(c.timestamp).getTime())
          );
          setOldestLoadedTime(oldest / 1000);
        } else {
          // No more data available
          setOldestLoadedTime(beforeTime);
        }
      } catch (error) {
        console.error("Error loading more historical data:", error);
      } finally {
        setIsLoadingMore(false);
      }
    },
    [selectedSymbol, selectedTimeframe, isLoadingMore, oldestLoadedTime, setCandles]
  );

  // Set up scroll listener for lazy loading
  useEffect(() => {
    if (!chartRef.current) return;

    const chart = chartRef.current;
    let isSubscribed = true;

    const handleVisibleTimeRangeChange = () => {
      if (!isSubscribed || isLoadingMore) return;

      const visibleRange = chart.timeScale().getVisibleRange();
      if (!visibleRange || !visibleRange.from) return;

      // Clear any pending timeout
      if (loadMoreTimeoutRef.current) {
        clearTimeout(loadMoreTimeoutRef.current);
      }

      // Debounce the load more request
      loadMoreTimeoutRef.current = setTimeout(() => {
        if (!isSubscribed) return;

        // Check if user scrolled to the left (older data)
        // Load more if we're within 20% of the oldest loaded data
        // Convert Time to number (unix timestamp)
        const convertTimeToNumber = (time: Time): number => {
          if (typeof time === 'number') return time;
          if (typeof time === 'string') return new Date(time).getTime() / 1000;
          // BusinessDay object - convert to timestamp
          const bd = time as { year: number; month: number; day: number };
          return new Date(bd.year, bd.month - 1, bd.day).getTime() / 1000;
        };
        
        const fromTime = convertTimeToNumber(visibleRange.from);
        const toTime = visibleRange.to ? convertTimeToNumber(visibleRange.to) : Date.now() / 1000;
        
        if (oldestLoadedTime) {
          const threshold = oldestLoadedTime + (toTime - fromTime) * 0.2;
          if (fromTime < threshold) {
            loadMoreHistoricalData(fromTime);
          }
        } else if (fromTime < Date.now() / 1000 - 86400) {
          // If we don't have oldestLoadedTime yet, load if scrolled back more than 1 day
          loadMoreHistoricalData(fromTime);
        }
      }, 300); // 300ms debounce
    };

    // Subscribe to visible time range changes
    // Note: TradingView Lightweight Charts doesn't provide an unsubscribe method
    // We use the isSubscribed flag to prevent callbacks after unmount
    chart.timeScale().subscribeVisibleTimeRangeChange(handleVisibleTimeRangeChange);

    return () => {
      isSubscribed = false;
      if (loadMoreTimeoutRef.current) {
        clearTimeout(loadMoreTimeoutRef.current);
      }
      // Note: TradingView doesn't provide unsubscribe, but setting isSubscribed = false
      // prevents the callback from executing after cleanup
    };
  }, [oldestLoadedTime, isLoadingMore, loadMoreHistoricalData]);

  // Update candles data
  useEffect(() => {
    if (!seriesRef.current || !candles.length) return;

    const filteredCandles = candles.filter(
      (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
    );

    const chartData: CandlestickData[] = filteredCandles
      .map((candle) => ({
        time: (new Date(candle.timestamp).getTime() / 1000) as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }))
      .sort((a, b) => (a.time as number) - (b.time as number)); // Sort ascending by time

    // Update the series data
    // Note: setData replaces all data, so we need to pass the complete sorted array
    seriesRef.current.setData(chartData);

    // Update oldest loaded time if we have new data
    if (chartData.length > 0) {
      const oldest = Math.min(...chartData.map((d) => d.time as number));
      if (!oldestLoadedTime || oldest < oldestLoadedTime) {
        setOldestLoadedTime(oldest);
      }
    }
    
    // Fit content only on initial load or symbol/timeframe change
    if (chartRef.current && chartData.length > 0) {
      // Only fit content if we don't have a visible range set (initial load)
      const visibleRange = chartRef.current.timeScale().getVisibleRange();
      if (!visibleRange) {
        chartRef.current.timeScale().fitContent();
      }
    }
  }, [candles, selectedSymbol, selectedTimeframe, oldestLoadedTime]);

  // Reset oldest loaded time when symbol or timeframe changes
  useEffect(() => {
    setOldestLoadedTime(null);
  }, [selectedSymbol, selectedTimeframe]);

  // Render overlays - ensure arrays are always arrays
  const currentSwings = Array.isArray(swingPoints)
    ? swingPoints.filter(
        (s) => s.symbol === selectedSymbol && s.timeframe === selectedTimeframe
      )
    : [];
  const currentSR = Array.isArray(srLevels)
    ? srLevels.filter(
        (s) => s.symbol === selectedSymbol && s.timeframe === selectedTimeframe
      )
    : [];

  return (
    <div className="relative w-full h-full">
      <div ref={chartContainerRef} className="w-full" style={{ height: `${height}px` }} />
      
      {chartSettings.showSwings && (
        <SwingMarkers
          chart={chartRef.current}
          series={seriesRef.current}
          swings={currentSwings}
          candles={candles.filter(
            (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
          )}
        />
      )}
      
      {chartSettings.showFibs && latestSignal && (
        <FibonacciOverlay
          chart={chartRef.current}
          signal={latestSignal}
          swings={currentSwings}
        />
      )}
      
      {chartSettings.showOrderBlocks && latestSignal && (
        <OrderBlockOverlay
          chart={chartRef.current}
          signal={latestSignal}
          candles={candles.filter(
            (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
          )}
        />
      )}
      
      {chartSettings.showSR && (
        <SupportResistanceLines
          chart={chartRef.current}
          series={seriesRef.current}
          srLevels={currentSR}
        />
      )}
      
      {chartSettings.showEntrySLTP && latestSignal && (
        <EntrySlTpLines
          chart={chartRef.current}
          series={seriesRef.current}
          signal={latestSignal}
        />
      )}
    </div>
  );
}

