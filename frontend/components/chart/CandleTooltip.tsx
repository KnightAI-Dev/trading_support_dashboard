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
  left: number;
  top: number;
  anchor: "top" | "bottom";
}

const TOOLTIP_WIDTH = 220;
const TOOLTIP_HEIGHT = 150;
const TOOLTIP_PADDING = 12;

const clamp = (value: number, min: number, max: number) =>
  Math.min(Math.max(value, min), max);

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
      if (!param || !param.time || !param.point || !chartContainer) {
        setTooltipData(null);
        return;
      }

      const time = param.time;
      const point = param.point;

      // Find the candle at this time
      const candleTime =
        typeof time === "number"
          ? time * 1000
          : new Date(time as string).getTime();

      const candle = filteredCandles.find((c) => {
        const cTime = new Date(c.timestamp).getTime();
        // Allow 1 minute tolerance for matching
        return Math.abs(cTime - candleTime) < 60000;
      });

      if (!candle) {
        setTooltipData(null);
        return;
      }

      const containerWidth = chartContainer.clientWidth;
      const containerHeight = chartContainer.clientHeight;

      const anchor: "top" | "bottom" =
        point.y <= TOOLTIP_HEIGHT + TOOLTIP_PADDING ? "bottom" : "top";

      const maxLeft = Math.max(containerWidth - TOOLTIP_WIDTH - TOOLTIP_PADDING, TOOLTIP_PADDING);
      const maxTop = Math.max(containerHeight - TOOLTIP_HEIGHT - TOOLTIP_PADDING, TOOLTIP_PADDING);

      const left = clamp(
        point.x + TOOLTIP_PADDING,
        TOOLTIP_PADDING,
        maxLeft
      );

      const desiredTop =
        anchor === "top"
          ? point.y - TOOLTIP_HEIGHT - TOOLTIP_PADDING
          : point.y + TOOLTIP_PADDING;

      const top = clamp(desiredTop, TOOLTIP_PADDING, maxTop);

      setTooltipData({
        time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume,
        timestamp: candle.timestamp,
        left,
        top,
        anchor,
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

  const isUp =
    tooltipData.close !== null &&
    tooltipData.open !== null &&
    tooltipData.close >= tooltipData.open;

  const priceDelta =
    tooltipData.close !== null && tooltipData.open !== null
      ? tooltipData.close - tooltipData.open
      : null;
  const priceDeltaPct =
    priceDelta !== null &&
    tooltipData.open !== null &&
    tooltipData.open !== 0
      ? (priceDelta / tooltipData.open) * 100
      : null;

  return (
    <div
      ref={tooltipRef}
      className="absolute z-50 bg-card border border-border rounded-lg shadow-lg p-3 pointer-events-none w-[220px]"
      style={{
        left: `${tooltipData.left}px`,
        top: `${tooltipData.top}px`,
      }}
    >
      <div className="space-y-2 text-sm">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{selectedSymbol} · {selectedTimeframe}</span>
          {tooltipData.timestamp && (
            <span>{formatTimestamp(tooltipData.timestamp)}</span>
          )}
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Open</span>
            <span className="font-medium">{formatPrice(tooltipData.open)}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">High</span>
            <span className="font-medium text-green-500">
              {formatPrice(tooltipData.high)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Low</span>
            <span className="font-medium text-red-500">
              {formatPrice(tooltipData.low)}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Close</span>
            <span
              className={`font-medium ${
                isUp ? "text-green-500" : "text-red-500"
              }`}
            >
              {formatPrice(tooltipData.close)}
            </span>
          </div>
          {priceDelta !== null && priceDeltaPct !== null && (
            <div className="flex items-center justify-between col-span-2 border-t border-border pt-1">
              <span className="text-muted-foreground">Δ (O→C)</span>
              <span
                className={`font-semibold ${
                  priceDelta >= 0 ? "text-green-500" : "text-red-500"
                }`}
              >
                {formatPrice(priceDelta)} ({priceDeltaPct.toFixed(2)}%)
              </span>
            </div>
          )}
          <div className="flex items-center justify-between col-span-2">
            <span className="text-muted-foreground">Volume</span>
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

