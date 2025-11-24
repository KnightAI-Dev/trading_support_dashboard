"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useMarketStore } from "@/stores/useMarketStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  fetchCandles,
  fetchSwingPoints,
  fetchSRLevels,
  fetchLatestSignal,
  fetchMarketMetadata,
  fetchAlertsForSwings,
  fetchSignals,
} from "@/lib/api";
import { TradingSignal } from "@/lib/api";
import { SwingPoint } from "@/lib/api";
import { Timeframe } from "@/lib/types";
import { ChartContainer } from "@/components/chart/ChartContainer";
import { SymbolManager } from "@/components/ui/SymbolManager";
import { useSymbolData } from "@/hooks/useSymbolData";
import { TimeframeSelector } from "@/components/ui/TimeframeSelector";
import { ConfluenceBadges } from "@/components/ui/ConfluenceBadge";
import { MarketScore } from "@/components/ui/MarketScore";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { formatPrice, formatTimestamp } from "@/lib/utils";
import { Settings, TrendingUp, TrendingDown, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";

const SYMBOL_MANAGER_WIDTH_KEY = "symbol_manager_width";
const DEFAULT_SIDEBAR_WIDTH = 320; // Default width in pixels
const MIN_SIDEBAR_WIDTH = 240; // Minimum width
const MAX_SIDEBAR_WIDTH = 600; // Maximum width

export default function DashboardPage() {
  const {
    selectedSymbol,
    selectedTimeframe,
    availableSymbols,
    availableTimeframes,
    symbolTimeframes,
    latestSignal,
    chartSettings,
    updateChartSettings,
    setCandles,
    setSwingPoints,
    setSRLevels,
    setLatestSignal,
    setSelectedSymbol,
    setSelectedTimeframe,
    setMarketMetadata,
    setLoading,
    setError,
  } = useMarketStore();
  
  // Get current swing points for refresh function
  const currentSwingPoints = useMarketStore((state) => state.swingPoints);

  // State for refresh button loading
  const [isRefreshingSwings, setIsRefreshingSwings] = useState(false);
  
  // State for signal navigation
  const [allSignals, setAllSignals] = useState<TradingSignal[]>([]);
  const [currentSignalIndex, setCurrentSignalIndex] = useState<number>(0);
  const [isLoadingSignals, setIsLoadingSignals] = useState(false);

  // Function to refresh swing high/low points from backend
  const refreshSwingPoints = useCallback(async () => {
    setIsRefreshingSwings(true);
    try {
      // Send symbol and timeframe to backend to get alert data from database
      const alerts = await fetchAlertsForSwings(selectedSymbol, selectedTimeframe, 100);

      // Extract swing points from alerts returned by backend
      const swingPointsMap = new Map<string, SwingPoint>(); // Use Map to prevent duplicates
      
      alerts.forEach((alert) => {
        if (alert.swing_high && alert.swing_high_timestamp) {
          // Create a unique key for this swing point
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
          // Create a unique key for this swing point
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

      // Convert Map to array and sort by timestamp in ascending order
      const uniqueSwingPoints = Array.from(swingPointsMap.values()).sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );
      
      // Only show swing points for the selected symbol and timeframe
      // Remove all other swing points and only keep the ones for current symbol/timeframe
      setSwingPoints(uniqueSwingPoints);
      
      // Also update the latest signal if we have alerts
      if (alerts.length > 0) {
        // Sort alerts by timestamp descending to get the latest
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

  // Resizable sidebar width state
  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(SYMBOL_MANAGER_WIDTH_KEY);
      if (stored) {
        const width = parseInt(stored, 10);
        return Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, width));
      }
    }
    return DEFAULT_SIDEBAR_WIDTH;
  });

  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const resizeStartX = useRef<number>(0);
  const resizeStartWidth = useRef<number>(0);

  // Persist width to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(SYMBOL_MANAGER_WIDTH_KEY, sidebarWidth.toString());
    }
  }, [sidebarWidth]);

  // Handle resize start
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    resizeStartX.current = e.clientX;
    resizeStartWidth.current = sidebarWidth;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [sidebarWidth]);

  // Handle resize
  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - resizeStartX.current;
      const newWidth = Math.max(
        MIN_SIDEBAR_WIDTH,
        Math.min(MAX_SIDEBAR_WIDTH, resizeStartWidth.current + deltaX)
      );
      setSidebarWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  // Handle window resize for responsiveness
  useEffect(() => {
    const handleResize = () => {
      if (typeof window !== "undefined" && sidebarRef.current) {
        const maxWidth = window.innerWidth * 0.5; // Max 50% of screen width
        if (sidebarWidth > maxWidth) {
          setSidebarWidth(Math.min(maxWidth, MAX_SIDEBAR_WIDTH));
        }
      }
    };

    window.addEventListener("resize", handleResize);
    handleResize(); // Initial check

    return () => window.removeEventListener("resize", handleResize);
  }, [sidebarWidth]);

  // Initialize WebSocket connection
  useWebSocket(selectedSymbol, selectedTimeframe);

  // Fetch symbol data for SymbolManager
  const { symbols } = useSymbolData();
  const symbolData = Array.isArray(symbols) ? symbols : [];

  // Load symbol/timeframe metadata
  const loadMetadata = useCallback(async () => {
      try {
        const metadata = await fetchMarketMetadata();
        setMarketMetadata(metadata);
      } catch (error) {
        console.error("Error loading market metadata:", error);
      }
  }, [setMarketMetadata]);

  useEffect(() => {
    let isMounted = true;

    const load = async () => {
      await loadMetadata();
    };

    loadMetadata();

    // Listen for ingestion config updates
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

  useEffect(() => {
    if (availableSymbols.length && !availableSymbols.includes(selectedSymbol)) {
      setSelectedSymbol(availableSymbols[0]);
    }
  }, [availableSymbols, selectedSymbol, setSelectedSymbol]);

  // Ensure timeframe stays valid for selected symbol
  useEffect(() => {
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
    selectedSymbol,
    selectedTimeframe,
    symbolTimeframes,
    availableTimeframes,
    setSelectedTimeframe,
  ]);

  // Fetch initial data
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const [candles] = await Promise.all([
          fetchCandles(selectedSymbol, selectedTimeframe, 1000),
          // fetchSwingPoints(selectedSymbol, selectedTimeframe),
          // fetchSRLevels(selectedSymbol, selectedTimeframe),
          // fetchLatestSignal(selectedSymbol),
        ]);

        setCandles(candles);
      } catch (error) {
        console.error("Error loading data:", error);
        setError("Failed to load market data");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [selectedSymbol, selectedTimeframe, setCandles, setLoading, setError]);

  // Fetch all signals for the selected symbol and timeframe
  useEffect(() => {
    const loadSignals = async () => {
      setIsLoadingSignals(true);
      try {
        const signals = await fetchSignals({
          symbol: selectedSymbol,
          limit: 1000,
        });
        
        // Filter signals by timeframe and sort by timestamp descending (newest first)
        const filteredSignals = signals
          .filter((s) => s.timeframe === selectedTimeframe)
          .sort((a, b) => 
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
          );
        
        setAllSignals(filteredSignals);
        
        // Set the first signal (latest) as the current signal
        if (filteredSignals.length > 0) {
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
  }, [selectedSymbol, selectedTimeframe, setLatestSignal]);

  // Update displayed signal when index changes
  useEffect(() => {
    if (allSignals.length > 0 && currentSignalIndex >= 0 && currentSignalIndex < allSignals.length) {
      setLatestSignal(allSignals[currentSignalIndex]);
    }
  }, [currentSignalIndex, allSignals, setLatestSignal]);

  // Navigation functions
  const handlePreviousSignal = () => {
    if (currentSignalIndex < allSignals.length - 1) {
      setCurrentSignalIndex(currentSignalIndex + 1);
    }
  };

  const handleNextSignal = () => {
    if (currentSignalIndex > 0) {
      setCurrentSignalIndex(currentSignalIndex - 1);
    }
  };

  const marketScore = latestSignal?.market_score || 0;

  return (
    <div className="flex h-screen bg-background">
      {/* Symbol Manager Sidebar */}
      <div
        ref={sidebarRef}
        className="flex-shrink-0 border-r border-border overflow-hidden"
        style={{ width: `${sidebarWidth}px` }}
      >
        <SymbolManager
          symbols={symbolData}
          onSelect={(symbol) => setSelectedSymbol(symbol as any)}
          className="h-full"
        />
      </div>
      
      {/* Resize Handle */}
      <div
        className="flex-shrink-0 w-1 bg-border hover:bg-primary/50 cursor-col-resize transition-colors relative group"
        onMouseDown={handleResizeStart}
      >
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-2" />
        {isResizing && (
          <div className="absolute inset-0 bg-primary/30" />
        )}
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 min-w-0">
        <div className="max-w-[1920px] mx-auto space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Trading Dashboard</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Real-time market structure analysis
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Link href="/settings">
                <Button variant="outline" size="sm">
                  <Settings className="h-4 w-4 mr-2" />
                  Settings
                </Button>
              </Link>
              <Link href="/signals">
                <Button variant="outline" size="sm">
                  Signals Table
                </Button>
              </Link>
            </div>
          </div>
          {/* Controls Bar */}
          <div className="flex flex-wrap items-center gap-4 p-4 bg-card rounded-lg border">
            <div className="flex items-center gap-2">
              <Label htmlFor="timeframe">Timeframe:</Label>
              <TimeframeSelector />
            </div>
            <div className="flex-1" />

            {/* Chart Toggle Controls - Swings and Entry/SL/TP are always shown */}
            <div className="flex items-center gap-4 flex-wrap">
              {/* Removed Fibs, OB, S/R toggles - they are hidden by default */}
              <div className="flex items-center gap-2">
                <Switch
                  id="show-swings"
                  checked={chartSettings.showSwings}
                  onCheckedChange={(checked: boolean) =>
                    updateChartSettings({ showSwings: checked })
                  }
                />
                <Label htmlFor="show-swings" className="text-sm cursor-pointer">
                  Swings
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="show-entry"
                  checked={chartSettings.showEntrySLTP}
                  onCheckedChange={(checked: boolean) =>
                    updateChartSettings({ showEntrySLTP: checked })
                  }
                />
                <Label htmlFor="show-entry" className="text-sm cursor-pointer">
                  Entry/SL/TP
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="show-rsi"
                  checked={chartSettings.showRSI}
                  onCheckedChange={(checked: boolean) =>
                    updateChartSettings({ showRSI: checked })
                  }
                />
                <Label htmlFor="show-rsi" className="text-sm cursor-pointer">
                  RSI
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="show-tooltip"
                  checked={chartSettings.showTooltip}
                  onCheckedChange={(checked: boolean) =>
                    updateChartSettings({ showTooltip: checked })
                  }
                />
                <Label htmlFor="show-tooltip" className="text-sm cursor-pointer">
                  Tooltip
                </Label>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={refreshSwingPoints}
                disabled={isRefreshingSwings}
                className="flex items-center gap-2"
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshingSwings ? "animate-spin" : ""}`} />
                Refresh Swings
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {/* Main Chart Panel */}
            <div className="lg:col-span-3">
              <Card className="p-4">
                <div className="mb-4">
                  <div className="flex items-center justify-between">
                    <h2 className="text-lg font-semibold">
                      {selectedSymbol.replace("USDT", "/USDT")} - {selectedTimeframe}
                    </h2>
                    {latestSignal && (
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={latestSignal.direction === "long" ? "long" : "short"}
                        >
                          {latestSignal.direction.toUpperCase()}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {formatTimestamp(latestSignal.timestamp)}
                        </span>
                        {/* Signal Navigation */}
                        <div className="flex items-center gap-1 ml-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handlePreviousSignal}
                            disabled={currentSignalIndex >= allSignals.length - 1 || isLoadingSignals}
                            className="h-7 w-7 p-0"
                            title="Previous signal (older)"
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </Button>
                          <span className="text-xs text-muted-foreground px-2">
                            {allSignals.length > 0 
                              ? `${currentSignalIndex + 1} / ${allSignals.length}`
                              : "0 / 0"}
                          </span>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleNextSignal}
                            disabled={currentSignalIndex <= 0 || isLoadingSignals}
                            className="h-7 w-7 p-0"
                            title="Next signal (newer)"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                <ChartContainer height={600} />
              </Card>
            </div>

            {/* Sidebar */}
            <div className="space-y-4">
              {/* Market Score */}
              <Card className="p-6">
                <MarketScore score={marketScore} />
              </Card>

              {/* Signal Info */}
              {latestSignal ? (
                <Card className="p-4">
                  <h3 className="text-sm font-semibold mb-4">
                    Signal {allSignals.length > 0 ? `${currentSignalIndex + 1} / ${allSignals.length}` : ""}
                  </h3>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">Direction</span>
                      <Badge
                        variant={latestSignal.direction === "long" ? "long" : "short"}
                      >
                        {latestSignal.direction === "long" ? (
                          <TrendingUp className="h-3 w-3 mr-1" />
                        ) : (
                          <TrendingDown className="h-3 w-3 mr-1" />
                        )}
                        {latestSignal.direction.toUpperCase()}
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">Entry</span>
                      <span className="text-sm font-medium">
                        {formatPrice(latestSignal.entry1 || latestSignal.price)}
                      </span>
                    </div>

                    {latestSignal.sl && (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">Stop Loss</span>
                        <span className="text-sm font-medium text-red-400">
                          {formatPrice(latestSignal.sl)}
                        </span>
                      </div>
                    )}

                    {latestSignal.tp1 && (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">TP1</span>
                        <span className="text-sm font-medium text-green-400">
                          {formatPrice(latestSignal.tp1)}
                        </span>
                      </div>
                    )}

                    {latestSignal.tp2 && (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">TP2</span>
                        <span className="text-sm font-medium text-green-400">
                          {formatPrice(latestSignal.tp2)}
                        </span>
                      </div>
                    )}

                    {latestSignal.tp3 && (
                      <div className="flex items-center justify-between">
                        <span className="text-xs text-muted-foreground">TP3</span>
                        <span className="text-sm font-medium text-green-400">
                          {formatPrice(latestSignal.tp3)}
                        </span>
                      </div>
                    )}

                    {latestSignal.swing_high && latestSignal.swing_low && (
                      <>
                        <div className="flex items-center justify-between pt-2 border-t">
                          <span className="text-xs text-muted-foreground">Swing High</span>
                          <span className="text-sm font-medium">
                            {formatPrice(latestSignal.swing_high)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">Swing Low</span>
                          <span className="text-sm font-medium">
                            {formatPrice(latestSignal.swing_low)}
                          </span>
                        </div>
                      </>
                    )}

                    {latestSignal.confluence && (
                      <div className="pt-2 border-t">
                        <span className="text-xs text-muted-foreground block mb-2">
                          Confluence
                        </span>
                        <ConfluenceBadges confluence={latestSignal.confluence} />
                      </div>
                    )}

                    {latestSignal.risk_reward_ratio && (
                      <div className="flex items-center justify-between pt-2 border-t">
                        <span className="text-xs text-muted-foreground">Risk/Reward</span>
                        <span className="text-sm font-medium">
                          {latestSignal.risk_reward_ratio.toFixed(2)}x
                        </span>
                      </div>
                    )}
                  </div>
                </Card>
              ) : (
                <Card className="p-4">
                  <p className="text-sm text-muted-foreground text-center">
                    No signal available
                  </p>
                </Card>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
