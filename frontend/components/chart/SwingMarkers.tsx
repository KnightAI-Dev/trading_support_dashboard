"use client";

import { useEffect, useMemo, useRef } from "react";
import {
  IChartApi,
  ISeriesApi,
  ISeriesMarkersPluginApi,
  SeriesMarker,
  Time,
  createSeriesMarkers,
} from "lightweight-charts";
import { SwingPoint, Candle } from "@/lib/api";

interface SwingMarkersProps {
  chart: IChartApi | null;
  series: ISeriesApi<"Candlestick"> | null;
  swings: SwingPoint[];
  candles: Candle[];
}

const MATCH_TOLERANCE_MS = 60 * 1000; // 1 minute window
const MAX_SWING_MARKERS = 400;

export function SwingMarkers({
  chart,
  series,
  swings,
  candles,
}: SwingMarkersProps) {
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null);

  const preparedCandles = useMemo(() => {
    if (!candles.length) return [];
    return candles.map((candle) => ({
      candle,
      timeMs: new Date(candle.timestamp).getTime(),
    }));
  }, [candles]);

  const preparedSwings = useMemo(() => {
    if (!swings.length) return [];
    // swings are already sorted ascending in store, keep only the latest subset to reduce work
    const startIndex = Math.max(0, swings.length - MAX_SWING_MARKERS);
    return swings.slice(startIndex).map((swing) => ({
      swing,
      timeMs: new Date(swing.timestamp).getTime(),
    }));
  }, [swings]);

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

    if (!preparedSwings.length || !preparedCandles.length) {
      plugin.setMarkers([]);
      return;
    }

    const markers: SeriesMarker<Time>[] = [];
    let candleIndex = 0;

    for (const { swing, timeMs } of preparedSwings) {
      while (
        candleIndex < preparedCandles.length - 1 &&
        preparedCandles[candleIndex].timeMs < timeMs
      ) {
        candleIndex++;
      }

      let closestIndex = candleIndex;
      if (
        candleIndex > 0 &&
        Math.abs(preparedCandles[candleIndex - 1].timeMs - timeMs) <
          Math.abs(preparedCandles[closestIndex].timeMs - timeMs)
      ) {
        closestIndex = candleIndex - 1;
      }

      const matched = preparedCandles[closestIndex];
      if (!matched || Math.abs(matched.timeMs - timeMs) > MATCH_TOLERANCE_MS) {
        continue;
      }

      markers.push({
        time: (matched.timeMs / 1000) as Time,
        position: swing.type === "high" ? "aboveBar" : "belowBar",
        color: swing.type === "high" ? "#10b981" : "#ef4444",
        shape: "circle",
        size: 1.5,
        text: swing.type === "high" ? "SH" : "SL",
      });
    }

    plugin.setMarkers(markers);
  }, [chart, series, preparedSwings, preparedCandles]);

  return null;
}

