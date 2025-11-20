"use client";

import { useEffect, useRef, useState } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  Time,
  CandlestickData,
  ColorType,
} from "lightweight-charts";
import { useMarketStore } from "@/stores/useMarketStore";
import { Candle } from "@/lib/api";
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

  const {
    candles,
    selectedSymbol,
    selectedTimeframe,
    swingPoints,
    srLevels,
    latestSignal,
    chartSettings,
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

  // Update candles data
  useEffect(() => {
    if (!seriesRef.current || !candles.length) return;

    const filteredCandles = candles.filter(
      (c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe
    );

    const chartData: CandlestickData[] = filteredCandles.map((candle) => ({
      time: (new Date(candle.timestamp).getTime() / 1000) as Time,
      open: candle.open,
      high: candle.high,
      low: candle.low,
      close: candle.close,
    }));

    seriesRef.current.setData(chartData);
    
    // Fit content
    if (chartRef.current && chartData.length > 0) {
      chartRef.current.timeScale().fitContent();
    }
  }, [candles, selectedSymbol, selectedTimeframe]);

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

