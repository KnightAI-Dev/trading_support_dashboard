"use client";

import { memo, useMemo } from "react";
import { TradingSignal } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { formatPrice, formatTimestamp, cn } from "@/lib/utils";
import { TrendingDown, TrendingUp } from "lucide-react";
import type { SymbolItem } from "@/components/ui/SymbolManager";

interface SignalRowProps {
  signal: TradingSignal;
  symbols?: SymbolItem[];
}

const calculatePriceScore = (currentPrice: number | null | undefined, entryPrice: number): number => {
  if (!currentPrice || currentPrice <= 0 || entryPrice <= 0) return 0;
  const score = Math.abs(currentPrice - entryPrice) / currentPrice;
  return score * 100; // Convert to percentage
};

export const SignalRow = memo(
  ({ signal, symbols = [] }: SignalRowProps) => {
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
      if (score <= 1) return "text-emerald-400"; // Within 1% of entry
      if (score <= 3) return "text-amber-400"; // Within 3% of entry
      return "text-red-400"; // More than 3% away from entry
    }, [score]);

    const priceTargets = useMemo(
      () =>
        [signal.tp1, signal.tp2, signal.tp3]
          .filter((value): value is number => typeof value === "number"),
      [signal.tp1, signal.tp2, signal.tp3]
    );

    const stopLoss = useMemo(() => {
      return signal.sl ?? null;
    }, [signal.sl]);

    const swingHigh = useMemo(() => {
      return signal.swing_high ?? null;
    }, [signal.swing_high]);

    const swingHighTimestamp = useMemo(() => {
      return signal.swing_high_timestamp ? formatTimestamp(signal.swing_high_timestamp) : null;
    }, [signal.swing_high_timestamp]);

    const swingLow = useMemo(() => {
      return signal.swing_low ?? null;
    }, [signal.swing_low]);

    const swingLowTimestamp = useMemo(() => {
      return signal.swing_low_timestamp ? formatTimestamp(signal.swing_low_timestamp) : null;
    }, [signal.swing_low_timestamp]);

    return (
      <div
        className={cn(
          "grid grid-cols-[200px_100px_120px_100px_100px_100px_100px_120px_120px_120px_120px] gap-4 items-center w-full border-b border-border/60 bg-card/70 px-4 py-3 transition hover:bg-card/90",
          directionIsLong ? "hover:border-l-2 hover:border-l-emerald-500/50" : "hover:border-l-2 hover:border-l-red-500/50"
        )}
      >
        {/* Symbol & Direction */}
        <div className="flex items-center gap-2">
          <div className="font-semibold tracking-tight text-foreground">
            {signal.symbol.replace("USDT", "/USDT")}
          </div>
          <Badge variant={directionIsLong ? "long" : "short"} className="px-2 py-1 text-[11px]">
            {directionIsLong ? (
              <TrendingUp className="mr-1 h-3 w-3" />
            ) : (
              <TrendingDown className="mr-1 h-3 w-3" />
            )}
            {signal.direction?.toUpperCase()}
          </Badge>
          {signal.timeframe && (
            <span className="text-xs uppercase text-muted-foreground">{signal.timeframe}</span>
          )}
        </div>

        {/* Price Score */}
        <div className="text-center">
          <p className={cn("font-semibold text-sm", scoreStyles)}>
            {currentPrice ? `${score.toFixed(2)}%` : "-"}
          </p>
          <div className="mt-1 h-1 w-full rounded-full bg-muted">
            <div
              className={cn(
                "h-full rounded-full transition-all",
                score <= 1 ? "bg-emerald-400" : score <= 3 ? "bg-amber-400" : "bg-red-400"
              )}
              style={{ width: `${Math.min(score, 10)}%` }}
            />
          </div>
        </div>

        {/* Entry */}
        <div className="text-right">
          <p className="font-mono text-sm text-foreground">{formatPrice(entryPrice)}</p>
          <p className="text-[10px] text-muted-foreground">Entry</p>
        </div>

        {/* Stop Loss */}
        <div className="text-right">
          {stopLoss !== null ? (
            <>
              <p className="font-mono text-sm text-red-400">{formatPrice(stopLoss)}</p>
              <p className="text-[10px] text-muted-foreground">SL</p>
            </>
          ) : (
            <span className="text-muted-foreground text-xs">-</span>
          )}
        </div>

        {/* TP1 */}
        <div className="text-right">
          {signal.tp1 ? (
            <>
              <p className="font-mono text-sm text-foreground">{formatPrice(signal.tp1)}</p>
              <p className="text-[10px] text-muted-foreground">TP1</p>
            </>
          ) : (
            <span className="text-muted-foreground text-xs">-</span>
          )}
        </div>

        {/* TP2 */}
        <div className="text-right">
          {signal.tp2 ? (
            <>
              <p className="font-mono text-sm text-foreground">{formatPrice(signal.tp2)}</p>
              <p className="text-[10px] text-muted-foreground">TP2</p>
            </>
          ) : (
            <span className="text-muted-foreground text-xs">-</span>
          )}
        </div>

        {/* TP3 */}
        <div className="text-right">
          {signal.tp3 ? (
            <>
              <p className="font-mono text-sm text-foreground">{formatPrice(signal.tp3)}</p>
              <p className="text-[10px] text-muted-foreground">TP3</p>
            </>
          ) : (
            <span className="text-muted-foreground text-xs">-</span>
          )}
        </div>

        {/* Swing High */}
        <div className="text-right">
          {swingHigh !== null ? (
            <>
              <p className="font-mono text-sm text-emerald-400">{formatPrice(swingHigh)}</p>
              <p className="text-[10px] text-muted-foreground">Swing High</p>
              {swingHighTimestamp && (
                <p className="text-[9px] text-muted-foreground">{swingHighTimestamp}</p>
              )}
            </>
          ) : (
            <span className="text-muted-foreground text-xs">-</span>
          )}
        </div>

        {/* Swing Low */}
        <div className="text-right">
          {swingLow !== null ? (
            <>
              <p className="font-mono text-sm text-red-400">{formatPrice(swingLow)}</p>
              <p className="text-[10px] text-muted-foreground">Swing Low</p>
              {swingLowTimestamp && (
                <p className="text-[9px] text-muted-foreground">{swingLowTimestamp}</p>
              )}
            </>
          ) : (
            <span className="text-muted-foreground text-xs">-</span>
          )}
        </div>

        {/* Current Price */}
        <div className="text-right">
          <p className="font-mono text-sm font-medium text-foreground">
            {currentPrice ? formatPrice(currentPrice) : formatPrice(signal.price)}
          </p>
          <p className="text-[10px] text-muted-foreground">Current</p>
        </div>

        {/* Timestamp */}
        <div className="text-right">
          <p className="text-xs text-muted-foreground">{lastUpdated}</p>
        </div>
      </div>
    );
  },
  (prev, next) => prev.signal === next.signal && prev.symbols === next.symbols
);

SignalRow.displayName = "SignalRow";


