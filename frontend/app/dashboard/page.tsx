"use client";
import { useMarketStore } from "@/stores/useMarketStore";
import { useSymbolData } from "@/hooks/useSymbolData";
import { ChartContainer } from "@/components/chart/ChartContainer";
import { SymbolManager } from "@/components/ui/SymbolManager";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Settings } from "lucide-react";
import Link from "next/link";
import { ResizableSidebar } from "@/components/dashboard/ResizableSidebar";
import { ChartControls } from "@/components/dashboard/ChartControls";
import { ChartHeader } from "@/components/dashboard/ChartHeader";
import { SignalInfoPanel } from "@/components/dashboard/SignalInfoPanel";
import { useDashboardData } from "@/components/dashboard/useDashboardData";
import { ErrorBoundary } from "@/components/error/ErrorBoundary";

function DashboardSkeleton() {
  return (
    <div className="flex h-screen bg-background">
      <div className="flex-1 p-4 md:p-6">
        <div className="max-w-[1920px] mx-auto space-y-4">
          <div className="h-12 bg-card rounded animate-pulse" />
          <div className="h-16 bg-card rounded animate-pulse" />
          <div className="h-[600px] bg-card rounded animate-pulse" />
        </div>
      </div>
    </div>
  );
}

function DashboardContent() {
  const {
    selectedSymbol,
    selectedTimeframe,
    latestSignal,
  } = useMarketStore();

  const { symbols } = useSymbolData();
  const symbolData = Array.isArray(symbols) ? symbols : [];

  const currentSymbolData = symbolData.find((s) => s.symbol === selectedSymbol);
  const currentPrice = currentSymbolData?.price ?? null;
  const entryPrice = latestSignal?.entry1 || latestSignal?.price || null;
  const marketScore = latestSignal?.market_score || 0;

  const {
    refreshSwingPoints,
    isRefreshingSwings,
    allSignals,
    currentSignalIndex,
    isLoadingSignals,
    handlePreviousSignal,
    handleNextSignal,
  } = useDashboardData();

  // WebSocket is handled by WebSocketProvider in root layout
  // No need to call useWebSocket here

  return (
    <div className="flex h-screen bg-background">
      {/* Symbol Manager Sidebar */}
      <ResizableSidebar>
        <SymbolManager
          symbols={symbolData}
          onSelect={(symbol) => useMarketStore.getState().setSelectedSymbol(symbol as any)}
          className="h-full"
        />
      </ResizableSidebar>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 min-w-0">
        <div className="max-w-[1920px] mx-auto space-y-4">
          {/* Header */}
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
          <ChartControls
            onRefreshSwings={refreshSwingPoints}
            isRefreshingSwings={isRefreshingSwings}
          />

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {/* Main Chart Panel */}
            <div className="lg:col-span-3">
              <Card className="p-4">
                <ChartHeader
                  symbol={selectedSymbol}
                  timeframe={selectedTimeframe}
                  signal={latestSignal}
                  signalIndex={currentSignalIndex}
                  totalSignals={allSignals.length}
                  isLoadingSignals={isLoadingSignals}
                  onPreviousSignal={handlePreviousSignal}
                  onNextSignal={handleNextSignal}
                />
                <ChartContainer height={600} />
              </Card>
            </div>

            {/* Sidebar */}
            <SignalInfoPanel
              signal={latestSignal}
              currentPrice={currentPrice}
              entryPrice={entryPrice}
              marketScore={marketScore}
              signalIndex={currentSignalIndex}
              totalSignals={allSignals.length}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <ErrorBoundary>
      <DashboardContent />
    </ErrorBoundary>
  );
}
