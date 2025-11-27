"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  Time,
  CandlestickData,
  HistogramData,
  ColorType,
} from "lightweight-charts";
import { useMarketStore } from "@/stores/useMarketStore";
import { Candle, fetchCandles } from "@/lib/api";
import { SwingMarkers } from "./SwingMarkers";
import { FibonacciOverlay } from "./FibonacciOverlay";
import { OrderBlockOverlay } from "./OrderBlockOverlay";
import { SupportResistanceLines } from "./SupportResistanceLines";
import { EntrySlTpLines } from "./EntrySlTpLines";
import { RSIIndicator } from "./RSIIndicator";
import { CandleTooltip } from "./CandleTooltip";
import { MovingAverages } from "./MovingAverages";
import { Loader2 } from "lucide-react";

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
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const [isChartReady, setIsChartReady] = useState(false);
  const widthOverrideRef = useRef<number | undefined>(width);
  const windowResizeHandlerRef = useRef<(() => void) | null>(null);
  const [oldestLoadedTime, setOldestLoadedTime] = useState<number | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const loadMoreTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const prevCandlesRef = useRef<Candle[]>([]);

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

  // Initialize chart once
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const container = chartContainerRef.current;
    const resolvedWidth =
      typeof width === "number"
        ? width
        : container.clientWidth > 0
        ? container.clientWidth
        : 800;
    
    const resolvedHeight =
      typeof height === "number"
        ? height
        : container.clientHeight > 0
        ? container.clientHeight
        : 600;

    const chart = createChart(container, {
      width: Math.floor(resolvedWidth),
      height: resolvedHeight,
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

    // Add volume histogram series below candlesticks
    const volumeSeries = chart.addHistogramSeries({
      color: "#26a69a",
      priceFormat: {
        type: "volume",
      },
      priceScaleId: "", // Use separate price scale
      // Make volume bars less prominent
      baseLineVisible: false,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    // Configure the volume price scale to make it small and position it at the bottom
    volumeSeries.priceScale().applyOptions({
      scaleMargins: {
        top: 0.9, // Make volume chart very small (96% top margin = volume takes ~4% of space)
        bottom: 0.01, // Minimal bottom margin to keep it at the bottom
      },
    });

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;
    volumeSeriesRef.current = volumeSeries;
    setIsChartReady(true);

    const updateWidth = (nextWidth?: number) => {
      if (!chartRef.current || chartRef.current !== chart) return;
      if (typeof nextWidth !== "number" || nextWidth <= 0 || Number.isNaN(nextWidth)) {
        return;
      }
      try {
        chart.applyOptions({ width: Math.floor(nextWidth) });
      } catch (error) {
        console.warn("ChartContainer: Error resizing chart", error);
      }
    };

    const updateHeight = (nextHeight?: number) => {
      if (!chartRef.current || chartRef.current !== chart) return;
      if (typeof nextHeight !== "number" || nextHeight <= 0 || Number.isNaN(nextHeight)) {
        return;
      }
      try {
        chart.applyOptions({ height: Math.floor(nextHeight) });
      } catch (error) {
        console.warn("ChartContainer: Error resizing chart height", error);
      }
    };

    let resizeObserver: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver((entries) => {
        if (widthOverrideRef.current !== undefined) return;
        const entry = entries[0];
        if (!entry) return;
        updateWidth(entry.contentRect.width);
        // Update height if it's dynamic (not explicitly set)
        if (typeof height !== "number") {
          updateHeight(entry.contentRect.height);
        }
      });
      resizeObserver.observe(container);
    } else {
      const handleResize = () => {
        if (widthOverrideRef.current !== undefined) return;
        updateWidth(container.clientWidth);
        // Update height if it's dynamic (not explicitly set)
        if (typeof height !== "number") {
          updateHeight(container.clientHeight);
        }
      };
      windowResizeHandlerRef.current = handleResize;
      window.addEventListener("resize", handleResize);
      handleResize();
    }

    return () => {
      if (resizeObserver) {
        resizeObserver.disconnect();
      }
      if (windowResizeHandlerRef.current) {
        window.removeEventListener("resize", windowResizeHandlerRef.current);
        windowResizeHandlerRef.current = null;
      }
      // Clear refs before disposing to prevent use after disposal
      chartRef.current = null;
      seriesRef.current = null;
      volumeSeriesRef.current = null;
      // Dispose chart
      try {
        chart.remove();
      } catch (error) {
        // Chart might already be disposed, ignore
        console.warn("ChartContainer: Error disposing chart", error);
      }
    };
  }, []); // Run only once on mount

  // Reflect width prop changes without recreating the chart
  useEffect(() => {
    widthOverrideRef.current = width ?? undefined;
    if (!chartRef.current) return;

    if (typeof width === "number") {
      try {
        chartRef.current.applyOptions({ width: Math.floor(width) });
      } catch (error) {
        console.warn("ChartContainer: Error applying width override", error);
      }
    } else if (chartContainerRef.current) {
      const autoWidth = chartContainerRef.current.clientWidth;
      if (autoWidth > 0) {
        try {
          chartRef.current.applyOptions({ width: Math.floor(autoWidth) });
        } catch (error) {
          console.warn("ChartContainer: Error applying auto width", error);
        }
      }
    }
  }, [width]);

  // Reflect height prop changes without recreating the chart
  useEffect(() => {
    if (!chartRef.current) return;
    try {
      chartRef.current.applyOptions({ height: Math.floor(height) });
    } catch (error) {
      console.warn("ChartContainer: Error applying height", error);
    }
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
      if (!isSubscribed || isLoadingMore || !chartRef.current) return;

      // Check if chart is still valid before using it
      let visibleRange;
      try {
        visibleRange = chart.timeScale().getVisibleRange();
        if (!visibleRange || !visibleRange.from) return;
      } catch (error) {
        // Chart is disposed, stop processing
        isSubscribed = false;
        return;
      }

      // Clear any pending timeout
      if (loadMoreTimeoutRef.current) {
        clearTimeout(loadMoreTimeoutRef.current);
      }

      // Store visibleRange for use in setTimeout
      const currentVisibleRange = visibleRange;

      // Debounce the load more request
      loadMoreTimeoutRef.current = setTimeout(() => {
        if (!isSubscribed || !chartRef.current) return;

        // Check if chart is still valid before using stored range
        try {
          // Verify chart is still valid
          chart.timeScale().getVisibleRange();
        } catch (error) {
          // Chart is disposed, stop processing
          isSubscribed = false;
          return;
        }

        if (!currentVisibleRange || !currentVisibleRange.from) return;

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
        
        const fromTime = convertTimeToNumber(currentVisibleRange.from);
        const toTime = currentVisibleRange.to ? convertTimeToNumber(currentVisibleRange.to) : Date.now() / 1000;
        
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

  // Update candles data with optimized incremental updates
  useEffect(() => {
    // Wait for chart to be ready
    if (!seriesRef.current) return;
    
    // Check if series is still valid (not disposed)
    try {
      if (!seriesRef.current.setData) return;
    } catch (error) {
      // Series might be disposed
      return;
    }

    const filteredCandles = candles.filter(
      (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
    );
    
    // If no candles match, return early
    if (!filteredCandles.length) return;

    const prevFiltered = prevCandlesRef.current.filter(
      (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
    );

    // Check if this is initial load or symbol/timeframe changed
    const isInitialLoad = prevFiltered.length === 0;
    const symbolChanged = prevFiltered.length > 0 && 
      (prevFiltered[0]?.symbol !== filteredCandles[0]?.symbol || 
       prevFiltered[0]?.timeframe !== filteredCandles[0]?.timeframe);

    if (isInitialLoad || symbolChanged) {
      // Full data replacement for initial load or symbol/timeframe change
      const sortedCandles = [...filteredCandles].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );

      const chartData: CandlestickData[] = sortedCandles.map((candle) => ({
        time: (new Date(candle.timestamp).getTime() / 1000) as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      }));

      // Volume data with color based on candle direction (green for up, red for down)
      // Using lower opacity colors to make volume less prominent
      const volumeData: HistogramData[] = sortedCandles.map((candle) => ({
        time: (new Date(candle.timestamp).getTime() / 1000) as Time,
        value: candle.volume,
        color: candle.close >= candle.open ? "#10b98180" : "#ef444480", // Green/red with 50% opacity
      }));

      try {
        if (seriesRef.current) {
          seriesRef.current.setData(chartData);
        }
        if (volumeSeriesRef.current) {
          volumeSeriesRef.current.setData(volumeData);
        }
      } catch (error) {
        // Series might be disposed, ignore
        console.warn("ChartContainer: Series is disposed", error);
        return;
      }

      // Update oldest loaded time if we have new data
      if (chartData.length > 0) {
        const oldest = Math.min(...chartData.map((d) => d.time as number));
        if (!oldestLoadedTime || oldest < oldestLoadedTime) {
          setOldestLoadedTime(oldest);
        }
      }
      
      // Fit content only on initial load or symbol/timeframe change
      try {
        if (chartRef.current && chartData.length > 0) {
          // Check if chart is still valid
          if (!chartRef.current.timeScale) return;
          const visibleRange = chartRef.current.timeScale().getVisibleRange();
          if (!visibleRange) {
            chartRef.current.timeScale().fitContent();
          }
        }
      } catch (error) {
        // Chart might be disposed, ignore
        console.warn("ChartContainer: Chart is disposed", error);
      }
    } else {
      // Incremental updates - only update new/changed candles
      const prevMap = new Map(
        prevFiltered.map(c => [c.timestamp, c])
      );
      
      // Find new or updated candles
      const newOrUpdatedCandles = filteredCandles.filter(c => {
        const prev = prevMap.get(c.timestamp);
        // New candle or price/volume changed (for real-time updates)
        return !prev || 
               prev.open !== c.open || 
               prev.high !== c.high || 
               prev.low !== c.low || 
               prev.close !== c.close ||
               prev.volume !== c.volume;
      });

      // Check if we have any candles older than the oldest loaded time
      // If so, we need to rebuild the entire dataset because update() can't update older data
      const hasOlderData = oldestLoadedTime !== null && newOrUpdatedCandles.some(candle => {
        const candleTime = new Date(candle.timestamp).getTime() / 1000;
        return candleTime < oldestLoadedTime!;
      });

      if (hasOlderData) {
        // Rebuild entire dataset with all candles sorted by time
        const sortedCandles = [...filteredCandles].sort(
          (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        const chartData: CandlestickData[] = sortedCandles.map((candle) => ({
          time: (new Date(candle.timestamp).getTime() / 1000) as Time,
          open: candle.open,
          high: candle.high,
          low: candle.low,
          close: candle.close,
        }));

        const volumeData: HistogramData[] = sortedCandles.map((candle) => ({
          time: (new Date(candle.timestamp).getTime() / 1000) as Time,
          value: candle.volume,
          color: candle.close >= candle.open ? "#10b98180" : "#ef444480", // 50% opacity
        }));

        try {
          if (seriesRef.current) {
            seriesRef.current.setData(chartData);
          }
          if (volumeSeriesRef.current) {
            volumeSeriesRef.current.setData(volumeData);
          }
        } catch (error) {
          // Series might be disposed, ignore
          console.warn("ChartContainer: Series is disposed", error);
          return;
        }

        // Update oldest loaded time
        if (chartData.length > 0) {
          const oldest = Math.min(...chartData.map((d) => d.time as number));
          setOldestLoadedTime(oldest);
        }
      } else {
        // Update chart with new/changed candles using update() for efficiency
        // This only works if all candles are newer than or equal to the oldest loaded time
        let rebuildNeeded = false;
        
        for (const candle of newOrUpdatedCandles) {
          const candleTime = (new Date(candle.timestamp).getTime() / 1000) as Time;
          
          // Update candlestick data
          if (seriesRef.current) {
            try {
              // Check if series is still valid
              if (!seriesRef.current.update) {
                rebuildNeeded = true;
                break;
              }
              seriesRef.current.update({
                time: candleTime,
                open: candle.open,
                high: candle.high,
                low: candle.low,
                close: candle.close,
              });
            } catch (error) {
              // If update fails (e.g., trying to update older data, or series is disposed), mark for rebuild
              console.warn("Update failed, will rebuild chart data:", error);
              rebuildNeeded = true;
              break; // Exit loop - we'll rebuild everything
            }
          }

          // Update volume data
          if (volumeSeriesRef.current) {
            try {
              // Check if series is still valid
              if (!volumeSeriesRef.current.update) {
                rebuildNeeded = true;
                break;
              }
              volumeSeriesRef.current.update({
                time: candleTime,
                value: candle.volume,
                color: candle.close >= candle.open ? "#10b98180" : "#ef444480", // 50% opacity
              });
            } catch (error) {
              // If volume update fails, mark for rebuild
              console.warn("Volume update failed, will rebuild:", error);
              rebuildNeeded = true;
              break;
            }
          }
        }

        // If update failed, rebuild entire dataset
        if (rebuildNeeded) {
          const sortedCandles = [...filteredCandles].sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
          );

          const chartData: CandlestickData[] = sortedCandles.map((c) => ({
            time: (new Date(c.timestamp).getTime() / 1000) as Time,
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
          }));

          const volumeData: HistogramData[] = sortedCandles.map((c) => ({
            time: (new Date(c.timestamp).getTime() / 1000) as Time,
            value: c.volume,
            color: c.close >= c.open ? "#10b98180" : "#ef444480", // 50% opacity
          }));
          
          try {
            if (seriesRef.current) {
              seriesRef.current.setData(chartData);
            }
            if (volumeSeriesRef.current) {
              volumeSeriesRef.current.setData(volumeData);
            }
          } catch (error) {
            // Series might be disposed, ignore
            console.warn("ChartContainer: Series is disposed", error);
            return;
          }
          
          if (chartData.length > 0) {
            const oldest = Math.min(...chartData.map((d) => d.time as number));
            setOldestLoadedTime(oldest);
          }
        }

        // Update oldest loaded time if we have new older data
        if (filteredCandles.length > 0) {
          const oldest = Math.min(
            ...filteredCandles.map((c) => new Date(c.timestamp).getTime() / 1000)
          );
          if (!oldestLoadedTime || oldest < oldestLoadedTime) {
            setOldestLoadedTime(oldest);
          }
        }
      }
    }

    // Update previous candles reference
    prevCandlesRef.current = candles;
  }, [candles, selectedSymbol, selectedTimeframe, oldestLoadedTime]);

  // Reset oldest loaded time and previous candles when symbol or timeframe changes
  useEffect(() => {
    setOldestLoadedTime(null);
    prevCandlesRef.current = [];
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

  const chartApi = isChartReady ? chartRef.current : null;
  const priceSeries = isChartReady ? seriesRef.current : null;

  // Calculate height for container
  const containerHeight = typeof height === "number" ? height : "100%";

  return (
    <div className="relative w-full h-full">
      {!isChartReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/80 backdrop-blur-sm z-10">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-6 w-6 text-primary animate-spin" />
            <p className="text-sm text-muted-foreground">Loading chart...</p>
          </div>
        </div>
      )}
      <div 
        ref={chartContainerRef} 
        className="w-full h-full" 
        style={typeof height === "number" ? { height: `${height}px` } : { height: "100%" }}
      />
      
      {/* Show Swing High/Low markers based on chart settings */}
      {chartSettings.showSwings && (
        <SwingMarkers
          chart={chartApi}
          series={priceSeries}
          swings={currentSwings}
          candles={candles.filter(
            (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
          )}
        />
      )}
      
      {/* Hide Fibs, OB, S/R - removed from display */}
      
      {/* Show Entry/SL/TP lines based on chart settings */}
      {chartSettings.showEntrySLTP && latestSignal && (
        <EntrySlTpLines
          chart={chartApi}
          series={priceSeries}
          signal={latestSignal}
        />
      )}

      {/* Show RSI indicator */}
      {chartSettings.showRSI && (
        <RSIIndicator
          chart={chartApi}
          candles={candles}
          selectedSymbol={selectedSymbol}
          selectedTimeframe={selectedTimeframe}
          period={14}
          height={chartSettings.rsiHeight}
        />
      )}

      {/* Candle Tooltip */}
      {chartSettings.showTooltip && (
        <CandleTooltip
          chart={chartApi}
          chartContainer={chartContainerRef.current}
          candles={candles}
          selectedSymbol={selectedSymbol}
          selectedTimeframe={selectedTimeframe}
        />
      )}

      {/* Moving Averages */}
      <MovingAverages
        chart={chartApi}
        candles={candles}
        selectedSymbol={selectedSymbol}
        selectedTimeframe={selectedTimeframe}
        showMA7={chartSettings.showMA7}
        showMA25={chartSettings.showMA25}
        showMA99={chartSettings.showMA99}
      />
    </div>
  );
}

