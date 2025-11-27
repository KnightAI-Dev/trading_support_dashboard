"use client";

import { useEffect, useState, useCallback } from "react";
import { useMarketStore } from "@/stores/useMarketStore";
import {
  fetchCandles,
  fetchMarketMetadata,
  fetchAlertsForSwings,
  fetchSignals,
  TradingSignal,
} from "@/lib/api";
import { SwingPoint } from "@/lib/api";
import { Timeframe } from "@/lib/types";

export function useDashboardData() {
  const {
    selectedSymbol,
    selectedTimeframe,
    availableSymbols,
    availableTimeframes,
    symbolTimeframes,
    setCandles,
    setSwingPoints,
    setLatestSignal,
    setMarketMetadata,
    setSelectedSymbol,
    setSelectedTimeframe,
    setLoading,
    setError,
  } = useMarketStore();

  const [isRefreshingSwings, setIsRefreshingSwings] = useState(false);
  const [allSignals, setAllSignals] = useState<TradingSignal[]>([]);
  const [currentSignalIndex, setCurrentSignalIndex] = useState<number>(0);
  const [isLoadingSignals, setIsLoadingSignals] = useState(false);
  const [isMetadataLoaded, setIsMetadataLoaded] = useState(false);

  // Load metadata FIRST - this should run on mount
  const loadMetadata = useCallback(async () => {
    try {
      const metadata = await fetchMarketMetadata();
      setMarketMetadata(metadata);
      setIsMetadataLoaded(true); // Mark metadata as loaded
    } catch (error) {
      console.error("Error loading market metadata:", error);
      // Even on error, mark as loaded to prevent infinite waiting
      setIsMetadataLoaded(true);
    }
  }, [setMarketMetadata]);

  // Load metadata on mount
  useEffect(() => {
    let isMounted = true;

    loadMetadata();

    const handleRefresh = () => {
      if (isMounted) {
        loadMetadata();
      }
    };

    window.addEventListener('refreshMarketData', handleRefresh);
    window.addEventListener('ingestionConfigUpdated', handleRefresh);

    return () => {
      isMounted = false;
      window.removeEventListener('refreshMarketData', handleRefresh);
      window.removeEventListener('ingestionConfigUpdated', handleRefresh);
    };
  }, [loadMetadata]);

  // Validate symbol AFTER metadata is loaded
  useEffect(() => {
    if (!isMetadataLoaded || !availableSymbols.length) return;
    
    if (!availableSymbols.includes(selectedSymbol)) {
      setSelectedSymbol(availableSymbols[0]);
    }
  }, [isMetadataLoaded, availableSymbols, selectedSymbol, setSelectedSymbol]);

  // Validate timeframe AFTER metadata is loaded
  useEffect(() => {
    if (!isMetadataLoaded) return;
    
    const symbolSpecificTimeframes =
      symbolTimeframes[selectedSymbol] && symbolTimeframes[selectedSymbol].length
        ? symbolTimeframes[selectedSymbol]
        : availableTimeframes;

    if (
      symbolSpecificTimeframes.length &&
      !symbolSpecificTimeframes.includes(selectedTimeframe)
    ) {
      setSelectedTimeframe(symbolSpecificTimeframes[0] as Timeframe);
    }
  }, [
    isMetadataLoaded,
    selectedSymbol,
    selectedTimeframe,
    symbolTimeframes,
    availableTimeframes,
    setSelectedTimeframe,
  ]);

  // Refresh swing points
  const refreshSwingPoints = useCallback(async () => {
    setIsRefreshingSwings(true);
    try {
      const alerts = await fetchAlertsForSwings(selectedSymbol, selectedTimeframe, 100);
      const swingPointsMap = new Map<string, SwingPoint>();

      alerts.forEach((alert) => {
        if (alert.swing_high && alert.swing_high_timestamp) {
          const key = `${alert.symbol}_${alert.timeframe}_high_${alert.swing_high_timestamp}_${alert.swing_high}`;
          if (!swingPointsMap.has(key)) {
            swingPointsMap.set(key, {
              id: Date.now() + swingPointsMap.size,
              symbol: alert.symbol,
              timeframe: alert.timeframe || selectedTimeframe,
              type: "high",
              price: alert.swing_high,
              timestamp: alert.swing_high_timestamp,
            });
          }
        }
        if (alert.swing_low && alert.swing_low_timestamp) {
          const key = `${alert.symbol}_${alert.timeframe}_low_${alert.swing_low_timestamp}_${alert.swing_low}`;
          if (!swingPointsMap.has(key)) {
            swingPointsMap.set(key, {
              id: Date.now() + swingPointsMap.size + 1000,
              symbol: alert.symbol,
              timeframe: alert.timeframe || selectedTimeframe,
              type: "low",
              price: alert.swing_low,
              timestamp: alert.swing_low_timestamp,
            });
          }
        }
      });

      const uniqueSwingPoints = Array.from(swingPointsMap.values()).sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );

      setSwingPoints(uniqueSwingPoints);

      if (alerts.length > 0) {
        const sortedAlerts = [...alerts].sort(
          (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
        setLatestSignal(sortedAlerts[0]);
      }
    } catch (error) {
      console.error("Error refreshing swing points:", error);
      setError("Failed to refresh swing points");
    } finally {
      setIsRefreshingSwings(false);
    }
  }, [selectedSymbol, selectedTimeframe, setSwingPoints, setLatestSignal, setError]);

  // Load initial data ONLY AFTER metadata is loaded
  useEffect(() => {
    if (!isMetadataLoaded) return; // Wait for metadata
    
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const candles = await fetchCandles(selectedSymbol, selectedTimeframe, 1000);
        setCandles(candles);
      } catch (error) {
        console.error("Error loading data:", error);
        setError("Failed to load market data");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [isMetadataLoaded, selectedSymbol, selectedTimeframe, setCandles, setLoading, setError]);

  // Load swing points ONLY AFTER metadata is loaded
  useEffect(() => {
    if (!isMetadataLoaded) return; // Wait for metadata
    refreshSwingPoints();
  }, [isMetadataLoaded, selectedSymbol, selectedTimeframe, refreshSwingPoints]);

  // Load signals ONLY AFTER metadata is loaded
  useEffect(() => {
    if (!isMetadataLoaded) return; // Wait for metadata
    
    const loadSignals = async () => {
      setIsLoadingSignals(true);
      try {
        const signals = await fetchSignals({
          symbol: selectedSymbol,
          limit: 1000,
        });

        const filteredSignals = signals
          .filter((s) => s.timeframe === selectedTimeframe)
          .sort((a, b) => 
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
          );

        setAllSignals(filteredSignals);

        let presetSignal: TradingSignal | null = null;
        try {
          const stored = sessionStorage.getItem('presetSignal');
          if (stored) {
            presetSignal = JSON.parse(stored);
            sessionStorage.removeItem('presetSignal');
          }
        } catch (e) {
          console.warn("Failed to parse preset signal:", e);
        }

        if (!presetSignal) {
          const currentLatestSignal = useMarketStore.getState().latestSignal;
          if (currentLatestSignal && 
              currentLatestSignal.symbol === selectedSymbol && 
              currentLatestSignal.timeframe === selectedTimeframe) {
            presetSignal = currentLatestSignal;
          }
        }

        if (presetSignal && 
            presetSignal.symbol === selectedSymbol && 
            presetSignal.timeframe === selectedTimeframe) {
          const presetIndex = filteredSignals.findIndex(
            (s) => {
              if (s.id && presetSignal!.id && s.id === presetSignal!.id) return true;
              if (s.timestamp === presetSignal!.timestamp && 
                  (s.entry1 || s.price) === (presetSignal!.entry1 || presetSignal!.price)) return true;
              if (s.timestamp === presetSignal!.timestamp && 
                  s.symbol === presetSignal!.symbol) return true;
              return false;
            }
          );

          if (presetIndex >= 0) {
            setCurrentSignalIndex(presetIndex);
            setLatestSignal(filteredSignals[presetIndex]);
          } else if (filteredSignals.length > 0) {
            setCurrentSignalIndex(0);
            setLatestSignal(presetSignal);
          } else {
            setCurrentSignalIndex(0);
            setLatestSignal(presetSignal || null);
          }
        } else if (filteredSignals.length > 0) {
          setCurrentSignalIndex(0);
          setLatestSignal(filteredSignals[0]);
        } else {
          setCurrentSignalIndex(0);
          setLatestSignal(null);
        }
      } catch (error) {
        console.error("Error loading signals:", error);
        setAllSignals([]);
        setCurrentSignalIndex(0);
        setLatestSignal(null);
      } finally {
        setIsLoadingSignals(false);
      }
    };

    loadSignals();
  }, [isMetadataLoaded, selectedSymbol, selectedTimeframe, setLatestSignal]);

  // Update signal when index changes
  useEffect(() => {
    if (allSignals.length > 0 && currentSignalIndex >= 0 && currentSignalIndex < allSignals.length) {
      setLatestSignal(allSignals[currentSignalIndex]);
    }
  }, [currentSignalIndex, allSignals, setLatestSignal]);

  // Navigation functions
  const handlePreviousSignal = useCallback(() => {
    setCurrentSignalIndex((prevIndex) => {
      if (allSignals.length > 0 && prevIndex < allSignals.length - 1) {
        return prevIndex + 1;
      }
      return prevIndex;
    });
  }, [allSignals]);

  const handleNextSignal = useCallback(() => {
    setCurrentSignalIndex((prevIndex) => {
      if (prevIndex > 0) {
        return prevIndex - 1;
      }
      return prevIndex;
    });
  }, []);

  return {
    refreshSwingPoints,
    isRefreshingSwings,
    allSignals,
    currentSignalIndex,
    isLoadingSignals,
    handlePreviousSignal,
    handleNextSignal,
    isMetadataLoaded, // Expose this so UI can show loading state
  };
}

