"use client";
import { useMemo, useCallback, memo } from "react";
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

// Memoized SymbolManager wrapper - only re-renders when symbols or onSelect changes
const MemoizedSymbolManager = memo(SymbolManager);

// Memoized SignalInfoPanel - only re-renders when its props change
const MemoizedSignalInfoPanel = memo(SignalInfoPanel);

// Memoized ChartHeader - only re-renders when its props change
const MemoizedChartHeader = memo(ChartHeader);

// Isolated component for the chart section - subscribes only to what it needs
function ChartSection() {
  const selectedSymbol = useMarketStore((state) => state.selectedSymbol);
  const selectedTimeframe = useMarketStore((state) => state.selectedTimeframe);
  const latestSignal = useMarketStore((state) => state.latestSignal);
  
  const {
    allSignals,
    currentSignalIndex,
    isLoadingSignals,
    handlePreviousSignal,
    handleNextSignal,
  } = useDashboardData();

  return (
    <div className="lg:col-span-3 flex flex-col min-h-0">
      <Card className="p-4 flex-1 flex flex-col min-h-0">
        <MemoizedChartHeader
          symbol={selectedSymbol}
          timeframe={selectedTimeframe}
          signal={latestSignal}
          signalIndex={currentSignalIndex}
          totalSignals={allSignals.length}
          isLoadingSignals={isLoadingSignals}
          onPreviousSignal={handlePreviousSignal}
          onNextSignal={handleNextSignal}
        />
        <ErrorBoundary
          fallback={
            <div className="flex-1 min-h-0 flex items-center justify-center text-sm text-muted-foreground">
              Unable to load chart. Please refresh the page or try again later.
            </div>
          }
        >
          <div className="flex-1 min-h-0 relative">
            <ChartContainer height={undefined} />
          </div>
        </ErrorBoundary>
      </Card>
    </div>
  );
}

// Isolated component for the signal info panel - subscribes only to what it needs
function SignalInfoSection() {
  const latestSignal = useMarketStore((state) => state.latestSignal);
  const selectedSymbol = useMarketStore((state) => state.selectedSymbol);
  
  const { symbols } = useSymbolData();
  
  // Memoize symbolData array conversion
  const symbolData = useMemo(
    () => Array.isArray(symbols) ? symbols : [],
    [symbols]
  );
  
  // Memoize currentSymbolData lookup - only recalculates when symbols or selectedSymbol changes
  const currentSymbolData = useMemo(
    () => symbolData.find((s) => s.symbol === selectedSymbol),
    [symbolData, selectedSymbol]
  );
  
  const currentPrice = useMemo(
    () => currentSymbolData?.price ?? null,
    [currentSymbolData]
  );
  
  const { allSignals, currentSignalIndex } = useDashboardData();
  
  const entryPrice = useMemo(
    () => latestSignal?.entry1 || latestSignal?.price || null,
    [latestSignal]
  );
  
  const marketScore = useMemo(
    () => latestSignal?.market_score || 0,
    [latestSignal]
  );

  return (
    <MemoizedSignalInfoPanel
      signal={latestSignal}
      currentPrice={currentPrice}
      entryPrice={entryPrice}
      marketScore={marketScore}
      signalIndex={currentSignalIndex}
      totalSignals={allSignals.length}
    />
  );
}

// Isolated component for the sidebar - only re-renders when symbols change
function SymbolSidebar() {
  const { symbols } = useSymbolData();
  
  // Memoize symbolData array conversion
  const symbolData = useMemo(
    () => Array.isArray(symbols) ? symbols : [],
    [symbols]
  );
  
  const setSelectedSymbol = useMarketStore((state) => state.setSelectedSymbol);
  
  const handleSelect = useCallback(
    (symbol: string) => {
      setSelectedSymbol(symbol as any);
    },
    [setSelectedSymbol]
  );

  return (
    <ResizableSidebar>
      <MemoizedSymbolManager
        symbols={symbolData}
        onSelect={handleSelect}
        className="h-full"
      />
    </ResizableSidebar>
  );
}

// Main dashboard content - minimal subscriptions
function DashboardContent() {
  const {
    refreshSwingPoints,
    isRefreshingSwings,
  } = useDashboardData();

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Symbol Manager Sidebar */}
      <SymbolSidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <div className="flex-shrink-0 p-4 md:p-6 pb-0">
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
          </div>
        </div>

        {/* Main Content Grid - Full Height */}
        <div className="flex-1 min-h-0 p-4 md:p-6 pt-4">
          <div className="max-w-[1920px] mx-auto h-full">
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-full">
              {/* Main Chart Panel */}
              <ChartSection />

              {/* Sidebar */}
              <SignalInfoSection />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return <DashboardContent />;
}
