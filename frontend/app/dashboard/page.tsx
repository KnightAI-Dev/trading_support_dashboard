"use client";

import { useEffect } from "react";
import { useMarketStore } from "@/stores/useMarketStore";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  fetchCandles,
  fetchSwingPoints,
  fetchSRLevels,
  fetchLatestSignal,
  fetchMarketMetadata,
} from "@/lib/api";
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
import { Settings, TrendingUp, TrendingDown } from "lucide-react";
import Link from "next/link";

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

  // Initialize WebSocket connection
  useWebSocket(selectedSymbol, selectedTimeframe);

  // Fetch symbol data for SymbolManager
  const { symbols } = useSymbolData();
  const symbolData = Array.isArray(symbols) ? symbols : [];

  // Load symbol/timeframe metadata
  useEffect(() => {
    let isMounted = true;

    const loadMetadata = async () => {
      try {
        const metadata = await fetchMarketMetadata();
        if (!isMounted) return;
        setMarketMetadata(metadata);
      } catch (error) {
        console.error("Error loading market metadata:", error);
      }
    };

    loadMetadata();

    return () => {
      isMounted = false;
    };
  }, [setMarketMetadata]);

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
        const [candles, swings, srLevels, signal] = await Promise.all([
          fetchCandles(selectedSymbol, selectedTimeframe, 200),
          fetchSwingPoints(selectedSymbol, selectedTimeframe),
          fetchSRLevels(selectedSymbol, selectedTimeframe),
          fetchLatestSignal(selectedSymbol),
        ]);

        setCandles(candles);
        setSwingPoints(swings);
        setSRLevels(srLevels);
        setLatestSignal(signal);
      } catch (error) {
        console.error("Error loading data:", error);
        setError("Failed to load market data");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [selectedSymbol, selectedTimeframe, setCandles, setSwingPoints, setSRLevels, setLatestSignal, setLoading, setError]);

  const marketScore = latestSignal?.market_score || 0;

  return (
    <div className="flex h-screen bg-background">
      {/* Symbol Manager Sidebar */}
      <SymbolManager
        symbols={symbolData}
        onSelect={(symbol) => setSelectedSymbol(symbol as any)}
        className="flex-shrink-0"
      />
      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
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

            {/* Chart Toggle Controls */}
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <Switch
                  id="show-fibs"
                  checked={chartSettings.showFibs}
                  onCheckedChange={(checked: boolean) =>
                    updateChartSettings({ showFibs: checked })
                  }
                />
                <Label htmlFor="show-fibs" className="text-sm cursor-pointer">
                  Fibs
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="show-ob"
                  checked={chartSettings.showOrderBlocks}
                  onCheckedChange={(checked: boolean) =>
                    updateChartSettings({ showOrderBlocks: checked })
                  }
                />
                <Label htmlFor="show-ob" className="text-sm cursor-pointer">
                  OB
                </Label>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  id="show-sr"
                  checked={chartSettings.showSR}
                  onCheckedChange={(checked: boolean) =>
                    updateChartSettings({ showSR: checked })
                  }
                />
                <Label htmlFor="show-sr" className="text-sm cursor-pointer">
                  S/R
                </Label>
              </div>
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

              {/* Latest Signal Info */}
              {latestSignal ? (
                <Card className="p-4">
                  <h3 className="text-sm font-semibold mb-4">Latest Signal</h3>
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
