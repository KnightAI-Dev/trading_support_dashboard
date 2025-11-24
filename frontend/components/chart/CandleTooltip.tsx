"use client";

import { useEffect, useRef, useState } from "react";
import { IChartApi, Time } from "lightweight-charts";
import { Candle } from "@/lib/api";
import { formatPrice, formatTimestamp } from "@/lib/utils";

interface CandleTooltipProps {
  chart: IChartApi | null;
  chartContainer: HTMLDivElement | null;
  candles: Candle[];
  selectedSymbol: string;
  selectedTimeframe: string;
}

interface TooltipData {
  time: Time | null;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  timestamp: string | null;
  x: number;
  y: number;
}

export function CandleTooltip({
  chart,
  chartContainer,
  candles,
  selectedSymbol,
  selectedTimeframe,
}: CandleTooltipProps) {
  const tooltipRef = useRef<HTMLDivElement>(null);
  const [tooltipData, setTooltipData] = useState<TooltipData | null>(null);

  useEffect(() => {
    if (!chart) return;

    const filteredCandles = candles
      .filter((c) => c.symbol === selectedSymbol && c.timeframe === selectedTimeframe)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    if (filteredCandles.length === 0) {
      setTooltipData(null);
      return;
    }

    const handleCrosshairMove = (param: any) => {
      if (!param || !param.time || !param.point) {
        setTooltipData(null);
        return;
      }

      const time = param.time;
      const point = param.point;

      // Find the candle at this time
      const candleTime = typeof time === "number" ? time * 1000 : new Date(time as string).getTime();
      
      const candle = filteredCandles.find((c) => {
        const cTime = new Date(c.timestamp).getTime();
        // Allow 1 minute tolerance for matching
        return Math.abs(cTime - candleTime) < 60000;
      });

      if (!candle) {
        setTooltipData(null);
        return;
      }

      // Use point coordinates directly (they're already relative to chart container)
      if (!chartContainer) {
        setTooltipData(null);
        return;
      }

      const x = point.x;
      const y = point.y;

      setTooltipData({
        time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume,
        timestamp: candle.timestamp,
        x,
        y,
      });
    };

    const handleMouseLeave = () => {
      setTooltipData(null);
    };

    chart.subscribeCrosshairMove(handleCrosshairMove);
    if (chartContainer) {
      chartContainer.addEventListener("mouseleave", handleMouseLeave);
    }

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove);
      if (chartContainer) {
        chartContainer.removeEventListener("mouseleave", handleMouseLeave);
      }
    };
  }, [chart, chartContainer, candles, selectedSymbol, selectedTimeframe]);

  if (!tooltipData) return null;

  const isUp = tooltipData.close !== null && tooltipData.open !== null && tooltipData.close >= tooltipData.open;

  return (
    <div
      ref={tooltipRef}
      className="absolute z-50 bg-card border border-border rounded-lg shadow-lg p-3 pointer-events-none min-w-[200px]"
      style={{
        left: `${tooltipData.x + 15}px`,
        top: `${tooltipData.y - 10}px`,
        transform: "translateY(-100%)",
      }}
    >
      <div className="space-y-1 text-sm">
        {tooltipData.timestamp && (
          <div className="text-xs text-muted-foreground mb-2 border-b border-border pb-1">
            {formatTimestamp(tooltipData.timestamp)}
          </div>
        )}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Open:</span>
            <span className="font-medium">{formatPrice(tooltipData.open)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">High:</span>
            <span className="font-medium text-green-500">{formatPrice(tooltipData.high)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Low:</span>
            <span className="font-medium text-red-500">{formatPrice(tooltipData.low)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Close:</span>
            <span className={`font-medium ${isUp ? "text-green-500" : "text-red-500"}`}>
              {formatPrice(tooltipData.close)}
            </span>
          </div>
          <div className="flex items-center justify-between col-span-2 pt-1 border-t border-border">
            <span className="text-muted-foreground">Volume:</span>
            <span className="font-medium">
              {tooltipData.volume?.toLocaleString(undefined, {
                maximumFractionDigits: 2,
              }) || "-"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

