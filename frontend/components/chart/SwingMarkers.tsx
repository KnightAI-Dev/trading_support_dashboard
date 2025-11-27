"use client";

import { useEffect, useRef } from "react";
import {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  SeriesMarker,
  Time,
  createSeriesMarkers,
} from "lightweight-charts";
import { SwingPoint } from "@/lib/api";
import { Candle } from "@/lib/api";

interface SwingMarkersProps {
  chart: IChartApi | null;
  series: ISeriesApi<"Candlestick"> | null;
  swings: SwingPoint[];
  candles: Candle[];
}

export function SwingMarkers({
  chart,
  series,
  swings,
  candles,
}: SwingMarkersProps) {
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  // Attach/detach the series markers plugin as the series changes
  useEffect(() => {
    if (!series) {
      if (markersPluginRef.current) {
        markersPluginRef.current.setMarkers([]);
        markersPluginRef.current.detach();
        markersPluginRef.current = null;
      }
      return;
    }

    // Always detach any existing plugin before attaching to a new series
    if (markersPluginRef.current) {
      markersPluginRef.current.setMarkers([]);
      markersPluginRef.current.detach();
    }

    markersPluginRef.current = createSeriesMarkers(series, [], {
      autoScale: false,
    });

    return () => {
      if (markersPluginRef.current) {
        markersPluginRef.current.setMarkers([]);
        markersPluginRef.current.detach();
        markersPluginRef.current = null;
      }
    };
  }, [series]);

  useEffect(() => {
    const plugin = markersPluginRef.current;
    if (!chart || !series || !plugin) {
      plugin?.setMarkers([]);
      return;
    }

    // Clear markers if prerequisites are missing
    if (!swings.length || !candles.length) {
      plugin.setMarkers([]);
      return;
    }

    const markers = swings
      .map((swing) => {
        const candle = candles.find(
          (c) =>
            Math.abs(new Date(c.timestamp).getTime() - new Date(swing.timestamp).getTime()) < 60000
        );

        if (!candle) return null;

        return {
          time: (new Date(swing.timestamp).getTime() / 1000) as Time,
          position: swing.type === "high" ? ("aboveBar" as const) : ("belowBar" as const),
          color: swing.type === "high" ? "#10b981" : "#ef4444",
          shape: "circle" as const,
          size: 1.5,
          text: swing.type === "high" ? "SH" : "SL",
        };
      })
      .filter((marker): marker is SeriesMarker<Time> => Boolean(marker))
      .sort((a, b) => (a.time as number) - (b.time as number));

    plugin.setMarkers(markers);
  }, [chart, series, swings, candles]);

  return null;
}

