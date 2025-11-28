"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  IChartApi,
  IPaneApi,
  ISeriesApi,
  Time,
  CandlestickData,
  HistogramData,
  createChart,
  AreaSeries,
} from "lightweight-charts";
import { useMarketStore } from "@/stores/useMarketStore";
import { shallow } from "zustand/shallow";
import { Candle, fetchCandles } from "@/lib/api";
import { SwingMarkers } from "./SwingMarkers";
import { EntrySlTpLines } from "./EntrySlTpLines";
import { CandleTooltip } from "./CandleTooltip";
import { DynamicIndicator } from "./DynamicIndicator";
import { Loader2 } from "lucide-react";
import { INDICATOR_REGISTRY } from "@/lib/indicators";

interface ChartContainerProps {
  width?: number;
  height?: number;
}

export function ChartContainer({
  width,
  height,
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
  const pricePaneRef = useRef<IPaneApi<Time> | null>(null);
  // Map to track panes for indicators that need separate panes
  const indicatorPanesRef = useRef<Map<string, IPaneApi<Time>>>(new Map());
  const [indicatorPanes, setIndicatorPanes] = useState<Map<string, IPaneApi<Time>>>(new Map());

  const {
    candles,
    selectedSymbol,
    selectedTimeframe,
    swingPoints,
    latestSignal,
    chartSettings,
    setCandles,
  } = useMarketStore(
    (state) => ({
      candles: state.candles,
      selectedSymbol: state.selectedSymbol,
      selectedTimeframe: state.selectedTimeframe,
      swingPoints: state.swingPoints,
      latestSignal: state.latestSignal,
      chartSettings: state.chartSettings,
      setCandles: state.setCandles,
    }),
    shallow
  );

  const currentCandles = useMemo(() => {
    if (!Array.isArray(candles)) return [];
    return candles.filter(
      (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
    );
  }, [candles, selectedSymbol, selectedTimeframe]);

  const currentSwings = useMemo(
    () =>
      Array.isArray(swingPoints)
        ? swingPoints.filter(
            (s) => s.symbol === selectedSymbol && s.timeframe === selectedTimeframe
          )
        : [],
    [swingPoints, selectedSymbol, selectedTimeframe]
  );

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

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    // Volume series will be created/removed based on Volume indicator selection
    // Don't create it here - it will be managed by the Volume indicator effect

    chartRef.current = chart;
    seriesRef.current = candlestickSeries;
    volumeSeriesRef.current = null; // Will be set when Volume indicator is active
    pricePaneRef.current = chart.panes()[0] ?? null;
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
      pricePaneRef.current = null;
      // Dispose chart
      try {
        chart.remove();
      } catch (error) {
        // Chart might already be disposed, ignore
        console.warn("ChartContainer: Error disposing chart", error);
      }
    };
  }, []); // Run only once on mount

  // Manage panes for dynamic indicators that need separate panes
  useEffect(() => {
    if (!isChartReady || !chartRef.current || !pricePaneRef.current) return;

    const chart = chartRef.current;
    const pricePane = pricePaneRef.current;
    const activeIndicators = chartSettings.activeIndicators || [];
    
    // Get indicators that need separate panes
    const indicatorsNeedingPanes = activeIndicators.filter((ind) => {
      const definition = INDICATOR_REGISTRY.find((d) => d.type === ind.type);
      return definition?.requiresSeparatePane && ind.visible;
    });

    // Create panes for indicators that need them
    const newPanes = new Map<string, IPaneApi<Time>>();
    
    indicatorsNeedingPanes.forEach((indicator) => {
      let pane = indicatorPanesRef.current.get(indicator.id);
      if (!pane) {
        try {
          pane = chart.addPane();
          pane.setPreserveEmptyPane(true);
          indicatorPanesRef.current.set(indicator.id, pane);
        } catch (error) {
          console.warn(`ChartContainer: Error adding pane for ${indicator.type}`, error);
          return;
        }
      }
      if (pane) {
        newPanes.set(indicator.id, pane);
      }
    });

    // Remove panes for indicators that are no longer active
    const activeIds = new Set(indicatorsNeedingPanes.map((ind) => ind.id));
    indicatorPanesRef.current.forEach((pane, id) => {
      if (!activeIds.has(id)) {
        try {
          const paneIndex = pane.paneIndex();
          chart.removePane(paneIndex);
        } catch (error) {
          console.warn(`ChartContainer: Error removing pane for ${id}`, error);
        }
        indicatorPanesRef.current.delete(id);
      }
    });

    setIndicatorPanes(new Map(newPanes));

    // Adjust stretch factors
    const totalPanes = 1 + indicatorsNeedingPanes.length; // 1 for price pane
    const paneHeight = Math.floor(100 / totalPanes);
    
    try {
      pricePane.setStretchFactor(Math.max(1, 100 - (paneHeight * indicatorsNeedingPanes.length)));
      newPanes.forEach((pane) => {
        pane.setStretchFactor(Math.max(1, paneHeight));
      });
    } catch (error) {
      console.warn("ChartContainer: Error adjusting pane sizes", error);
    }
  }, [isChartReady, chartSettings.activeIndicators]);

  // Manage Volume series creation/removal based on Volume indicator
  useEffect(() => {
    if (!isChartReady || !chartRef.current) return;

    const chart = chartRef.current;
    const activeIndicators = chartSettings.activeIndicators || [];
    const volumeIndicator = activeIndicators.find(
      (ind) => ind.type === "Volume" && ind.visible
    );

    if (volumeIndicator && !volumeSeriesRef.current) {
      // Create volume series
      try {
        const volumeSeries = chart.addSeries(HistogramSeries, {
          color: "#26a69a",
          priceFormat: {
            type: "volume",
          },
          priceScaleId: "", // Use separate price scale
          baseLineVisible: false,
          priceLineVisible: false,
          lastValueVisible: false,
        });

        // Configure the volume price scale to make it small and position it at the bottom
        volumeSeries.priceScale().applyOptions({
          scaleMargins: {
            top: 0.9, // Make volume chart very small (90% top margin = volume takes ~10% of space)
            bottom: 0.01, // Minimal bottom margin to keep it at the bottom
          },
        });

        volumeSeriesRef.current = volumeSeries;

        // Immediately populate volume data if we have candles
        const filteredCandles = currentCandles
          .filter((c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe)
          .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

        if (filteredCandles.length > 0) {
          const volumeData: HistogramData[] = filteredCandles.map((candle) => ({
            time: (new Date(candle.timestamp).getTime() / 1000) as Time,
            value: candle.volume,
            color: candle.close >= candle.open ? "#10b98180" : "#ef444480", // Green/red with 50% opacity
          }));
          volumeSeries.setData(volumeData);
        }
      } catch (error) {
        console.warn("ChartContainer: Error creating volume series", error);
      }
    } else if (!volumeIndicator && volumeSeriesRef.current) {
      // Remove volume series
      try {
        chart.removeSeries(volumeSeriesRef.current);
        volumeSeriesRef.current = null;
      } catch (error) {
        console.warn("ChartContainer: Error removing volume series", error);
        volumeSeriesRef.current = null;
      }
    }
  }, [isChartReady, chartSettings.activeIndicators, currentCandles, selectedSymbol, selectedTimeframe]);

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
    if (!chartRef.current || typeof height !== "number") return;
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
          const storeCandles = useMarketStore.getState().candles;
          
          // Separate candles for current symbol/timeframe and others
          const otherCandles = storeCandles.filter(
            (c) => !(c.symbol === selectedSymbol && c.timeframe === selectedTimeframe)
          );
          const filteredExisting = storeCandles.filter(
            (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
          );

          // Merge and deduplicate by timestamp for current symbol/timeframe
          const candleMap = new Map<string, Candle>();
          
          // Add existing candles for current symbol/timeframe
          filteredExisting.forEach((candle) => {
            candleMap.set(candle.timestamp, candle);
          });

          // Add new candles (overwrite duplicates to ensure freshest data)
          newCandles.forEach((candle) => {
            candleMap.set(candle.timestamp, candle);
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

    const filteredCandles = currentCandles;
    
    // If no candles match, clear previous reference and exit
    if (!filteredCandles.length) {
      prevCandlesRef.current = [];
      return;
    }

    const prevFiltered = prevCandlesRef.current;

    // Check if this is initial load or symbol/timeframe changed
    const isInitialLoad = prevFiltered.length === 0;
    const symbolChanged = prevFiltered.length > 0 && 
      (prevFiltered[0]?.symbol !== filteredCandles[0]?.symbol || 
       prevFiltered[0]?.timeframe !== filteredCandles[0]?.timeframe);
    const shouldForceFit = isInitialLoad || symbolChanged;

    const fitChartToContent = () => {
      if (!chartRef.current?.timeScale) return;
      try {
        chartRef.current.timeScale().fitContent();
      } catch (error) {
        console.warn("ChartContainer: Error fitting content", error);
      }
    };

    const resetPriceScale = () => {
      try {
        const priceScale = seriesRef.current?.priceScale();
        priceScale?.setAutoScale(true);
      } catch (error) {
        console.warn("ChartContainer: Error resetting price scale", error);
      }
    };

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
      
      if (chartData.length > 0 && shouldForceFit) {
        resetPriceScale();
        fitChartToContent();
      } else {
        try {
          if (chartRef.current && chartData.length > 0) {
            if (!chartRef.current.timeScale) return;
            const visibleRange = chartRef.current.timeScale().getVisibleRange();
            if (!visibleRange) {
              fitChartToContent();
            }
          }
        } catch (error) {
          console.warn("ChartContainer: Chart is disposed", error);
        }
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

        if (chartData.length > 0 && shouldForceFit) {
          resetPriceScale();
          fitChartToContent();
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

        if (chartData.length > 0 && shouldForceFit) {
          resetPriceScale();
          fitChartToContent();
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
    prevCandlesRef.current = filteredCandles;
  }, [currentCandles, oldestLoadedTime]);

  // Reset oldest loaded time and previous candles when symbol or timeframe changes
  useEffect(() => {
    setOldestLoadedTime(null);
    prevCandlesRef.current = [];
  }, [selectedSymbol, selectedTimeframe]);

  const chartApi = isChartReady ? chartRef.current : null;
  const priceSeries = isChartReady ? seriesRef.current : null;

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
          candles={currentCandles}
        />
      )}
      
      {/* Hide Fibs, OB, S/R - removed from display */}
      
      {/* Show Entry/SL/TP lines based on chart settings */}
      {chartSettings.showEntrySLTP && latestSignal && (
        <EntrySlTpLines
          chart={chartApi}
          series={priceSeries}
          signal={latestSignal}
          selectedSymbol={selectedSymbol}
          selectedTimeframe={selectedTimeframe}
        />
      )}

      {/* Candle Tooltip */}
      {chartSettings.showTooltip && (
        <CandleTooltip
          chart={chartApi}
          chartContainer={chartContainerRef.current}
          candles={currentCandles}
          selectedSymbol={selectedSymbol}
          selectedTimeframe={selectedTimeframe}
        />
      )}

      {/* Dynamic Indicators */}
      {(chartSettings.activeIndicators || []).map((indicator) => {
        if (!indicator.visible) return null;
        
        const definition = INDICATOR_REGISTRY.find((d) => d.type === indicator.type);
        const needsSeparatePane = definition?.requiresSeparatePane;
        const pane = needsSeparatePane 
          ? indicatorPanes.get(indicator.id) || null
          : pricePaneRef.current;

        if (needsSeparatePane && !pane) return null; // Pane not ready yet

        return (
          <DynamicIndicator
            key={indicator.id}
            chart={chartApi}
            pane={pane}
            candles={currentCandles}
            selectedSymbol={selectedSymbol}
            selectedTimeframe={selectedTimeframe}
            indicator={indicator}
          />
        );
      })}
    </div>
  );
}


