"use client";

import { memo, useMemo } from "react";
import { useRouter } from "next/navigation";
import { TradingSignal } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatPrice, formatTimestamp, cn } from "@/lib/utils";
import { TrendingDown, TrendingUp, ArrowRight } from "lucide-react";
import type { SymbolItem } from "@/components/ui/SymbolManager";
import { useMarketStore } from "@/stores/useMarketStore";
import { ConfluenceBadges } from "@/components/ui/ConfluenceBadge";

interface SignalRowProps {
  signal: TradingSignal;
  symbols?: SymbolItem[];
}

const calculatePriceScore = (currentPrice: number | null | undefined, entryPrice: number): number => {
  if (!currentPrice || currentPrice <= 0 || entryPrice <= 0) return Infinity; // Missing prices should be treated as invalid
  const score = Math.abs(currentPrice - entryPrice) / currentPrice;
  return score * 100; // Convert to percentage
};

export const SignalRow = memo(
  ({ signal, symbols = [] }: SignalRowProps) => {
    const router = useRouter();
    const { setSelectedSymbol, setSelectedTimeframe, setLatestSignal } = useMarketStore();
    const directionIsLong = signal.direction === "long";
    const entryPrice = signal.entry1 ?? signal.price ?? 0;
    
    // Get current price for this symbol
    const currentPrice = useMemo(() => {
      const symbolData = symbols.find((s) => s.symbol === signal.symbol);
      return symbolData?.price ?? null;
    }, [symbols, signal.symbol]);
    
    // Calculate score: abs(current_price - entry_price) / current_price
    const score = useMemo(() => {
      return calculatePriceScore(currentPrice, entryPrice);
    }, [currentPrice, entryPrice]);
    
    const lastUpdated = formatTimestamp(signal.timestamp);

    const scoreStyles = useMemo(() => {
      // Score is now a percentage (0-100+), lower is better (closer to entry)
      // Handle invalid/missing prices
      if (!isFinite(score)) return "text-muted-foreground";
      if (score <= 1) return "text-emerald-400"; // Within 1% of entry
      if (score <= 3) return "text-amber-400"; // Within 3% of entry
      return "text-red-400"; // More than 3% away from entry
    }, [score]);

    const stopLoss = signal.sl ?? null;
    const swingHigh = signal.swing_high ?? null;
    const swingLow = signal.swing_low ?? null;
    const swingHighTimestamp = signal.swing_high_timestamp ? formatTimestamp(signal.swing_high_timestamp) : null;
    const swingLowTimestamp = signal.swing_low_timestamp ? formatTimestamp(signal.swing_low_timestamp) : null;

    const handleViewChart = async (e: React.MouseEvent) => {
      e.stopPropagation(); // Prevent any parent click handlers
      try {
        // Set symbol and timeframe first
        setSelectedSymbol(signal.symbol as any);
        if (signal.timeframe) {
          setSelectedTimeframe(signal.timeframe as any);
        }
        // Set the signal in store
        setLatestSignal(signal);
        // Small delay to ensure state updates propagate
        await new Promise(resolve => setTimeout(resolve, 50));
        // Navigate to dashboard
        router.push("/dashboard");
      } catch (error) {
        console.error("Error navigating to dashboard:", error);
      }
    };

    return (
      <div
        className={cn(
          "grid grid-cols-[150px_100px_80px_100px_120px_100px_100px_100px_100px_100px_120px_120px_120px_150px_100px] gap-4 items-center w-full",
          "border-b border-border/50 bg-card px-4 py-2.5"
        )}
      >
        {/* Symbol */}
        <div className="font-semibold text-sm text-foreground">
          {signal.symbol.replace("USDT", "/USDT")}
        </div>

        {/* Direction */}
        <div>
          <Badge variant={directionIsLong ? "long" : "short"} className="px-2 py-0.5 text-[10px] font-medium">
            {directionIsLong ? (
              <TrendingUp className="mr-1 h-3 w-3" />
            ) : (
              <TrendingDown className="mr-1 h-3 w-3" />
            )}
            {signal.direction?.toUpperCase()}
          </Badge>
        </div>

        {/* Timeframe */}
        <div className="text-xs uppercase font-medium text-muted-foreground">
          {signal.timeframe || "-"}
        </div>

        {/* Price Score */}
        <div className="text-center">
          <p className={cn("font-semibold text-sm", scoreStyles)}>
            {currentPrice && isFinite(score) ? `${score.toFixed(2)}%` : "-"}
          </p>
          {currentPrice && isFinite(score) && (
            <div className="mt-1 h-1 w-full max-w-[60px] mx-auto rounded-full bg-muted/50">
              <div
                className={cn(
                  "h-full rounded-full",
                  score <= 1 ? "bg-emerald-400" : score <= 3 ? "bg-amber-400" : "bg-red-400"
                )}
                style={{ width: `${Math.min(score * 10, 100)}%` }}
              />
            </div>
          )}
        </div>

        {/* Current Price */}
        <div className="text-right">
          <p className="font-mono text-sm font-semibold text-foreground">
            {currentPrice ? formatPrice(currentPrice) : formatPrice(signal.price)}
          </p>
        </div>

        {/* Entry */}
        <div className="text-right">
          <p className="font-mono text-sm text-foreground/90">{formatPrice(entryPrice)}</p>
        </div>

        {/* Stop Loss */}
        <div className="text-right">
          {stopLoss !== null ? (
            <p className="font-mono text-sm text-red-400/90">{formatPrice(stopLoss)}</p>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* TP1 */}
        <div className="text-right">
          {signal.tp1 ? (
            <p className="font-mono text-sm text-emerald-400/90">{formatPrice(signal.tp1)}</p>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* TP2 */}
        <div className="text-right">
          {signal.tp2 ? (
            <p className="font-mono text-sm text-emerald-500/90">{formatPrice(signal.tp2)}</p>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* TP3 */}
        <div className="text-right">
          {signal.tp3 ? (
            <p className="font-mono text-sm text-emerald-600/90">{formatPrice(signal.tp3)}</p>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* Swing High */}
        <div className="text-right">
          {swingHigh !== null ? (
            <div>
              <p className="font-mono text-sm text-emerald-400/90">{formatPrice(swingHigh)}</p>
              {swingHighTimestamp && (
                <p className="text-[9px] text-muted-foreground/70 mt-0.5">{swingHighTimestamp}</p>
              )}
            </div>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* Swing Low */}
        <div className="text-right">
          {swingLow !== null ? (
            <div>
              <p className="font-mono text-sm text-red-400/90">{formatPrice(swingLow)}</p>
              {swingLowTimestamp && (
                <p className="text-[9px] text-muted-foreground/70 mt-0.5">{swingLowTimestamp}</p>
              )}
            </div>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* Timestamp */}
        <div className="text-right">
          <p className="text-xs text-muted-foreground/80">{lastUpdated}</p>
        </div>

        {/* Confluence */}
        <div>
          {signal.confluence ? (
            <ConfluenceBadges confluence={signal.confluence} />
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* Action Button */}
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={handleViewChart}
            className="h-7 px-2.5"
          >
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    );
  },
  (prev, next) => prev.signal === next.signal && prev.symbols === next.symbols
);

SignalRow.displayName = "SignalRow";


