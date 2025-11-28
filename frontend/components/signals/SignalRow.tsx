"use client";

import { memo, useMemo, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { TradingSignal } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatPrice, formatTimestamp, formatTimeDelta, cn } from "@/lib/utils";
import { TrendingDown, TrendingUp, ArrowRight } from "lucide-react";
import { useMarketStore } from "@/stores/useMarketStore";
import { ConfluenceBadges } from "@/components/ui/ConfluenceBadge";

interface SignalRowProps {
  signal: TradingSignal;
  currentPrice?: number | null;
}

const calculatePriceScore = (currentPrice: number | null | undefined, entryPrice: number): number => {
  if (!currentPrice || currentPrice <= 0 || entryPrice <= 0) return Infinity;
  const score = Math.abs(currentPrice - entryPrice) / currentPrice;
  return score * 100;
};

export const SignalRow = memo(
  ({ signal, currentPrice = null }: SignalRowProps) => {
    const router = useRouter();
    const { setSelectedSymbol, setSelectedTimeframe, setLatestSignal } = useMarketStore();
    const directionIsLong = signal.direction === "long";
    const entryPrice = signal.entry1 ?? signal.price ?? 0;
    
    // Calculate score: abs(current_price - entry_price) / current_price
    const score = useMemo(() => {
      return calculatePriceScore(currentPrice, entryPrice);
    }, [currentPrice, entryPrice]);
    
    const lastUpdated = formatTimestamp(signal.timestamp);

    const scoreStyles = useMemo(() => {
      if (!isFinite(score)) return "text-muted-foreground";
      if (score <= 1) return "text-emerald-400";
      if (score <= 3) return "text-amber-400";
      return "text-red-400";
    }, [score]);

    const stopLoss = signal.sl ?? null;
    const swingHigh = signal.swing_high ?? null;
    const swingLow = signal.swing_low ?? null;
    const swingHighTimestamp = signal.swing_high_timestamp ? formatTimestamp(signal.swing_high_timestamp) : null;
    const swingLowTimestamp = signal.swing_low_timestamp ? formatTimestamp(signal.swing_low_timestamp) : null;
    
    // Real-time time delta updates
    const [now, setNow] = useState(() => new Date());
    
    useEffect(() => {
      const interval = setInterval(() => {
        setNow(new Date());
      }, 1000);
      
      return () => clearInterval(interval);
    }, []);
    
    const swingHighTimeDelta = useMemo(() => {
      if (!signal.swing_high_timestamp) return null;
      const timestamp = typeof signal.swing_high_timestamp === "string" 
        ? new Date(signal.swing_high_timestamp) 
        : signal.swing_high_timestamp;
      return formatTimeDelta(timestamp);
    }, [signal.swing_high_timestamp, now]);
    
    const swingLowTimeDelta = useMemo(() => {
      if (!signal.swing_low_timestamp) return null;
      const timestamp = typeof signal.swing_low_timestamp === "string" 
        ? new Date(signal.swing_low_timestamp) 
        : signal.swing_low_timestamp;
      return formatTimeDelta(timestamp);
    }, [signal.swing_low_timestamp, now]);

    const handleViewChart = useCallback(async (e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        setSelectedSymbol(signal.symbol as any);
        if (signal.timeframe) {
          setSelectedTimeframe(signal.timeframe as any);
        }
        setLatestSignal(signal);
        await new Promise(resolve => setTimeout(resolve, 50));
        router.push("/dashboard");
      } catch (error) {
        console.error("Error navigating to dashboard:", error);
      }
    }, [signal, setSelectedSymbol, setSelectedTimeframe, setLatestSignal, router]);

    return (
      <div
        className={cn(
          "grid grid-cols-[150px_100px_80px_100px_100px_100px_100px_100px_100px_100px_120px_120px_80px_120px_100px] gap-4 items-center w-full",
          "border-b border-border/50 bg-card px-4 py-3"
        )}
        role="row"
        aria-label={`Signal for ${signal.symbol}`}
      >
        {/* Symbol */}
        <div className="font-semibold text-sm text-foreground">
          {signal.symbol.replace("USDT", "/USDT")}
        </div>

        {/* Direction */}
        <div>
          <Badge 
            variant={directionIsLong ? "long" : "short"} 
            className="px-2.5 py-1 text-[10px] font-medium"
          >
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
            <div className="mt-1.5 h-1 w-full max-w-[60px] mx-auto rounded-full bg-muted/50 overflow-hidden">
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
        <div className="text-center">
          <p className="font-mono text-sm font-semibold text-foreground">
            {currentPrice ? formatPrice(currentPrice) : formatPrice(signal.price)}
          </p>
        </div>

        {/* Entry */}
        <div className="text-center">
          <p className="font-mono text-sm text-foreground/90">{formatPrice(entryPrice)}</p>
        </div>

        {/* Stop Loss */}
        <div className="text-center">
          {stopLoss !== null && entryPrice > 0 ? (
            <div>
              <p className="font-mono text-sm text-red-400/90">{formatPrice(stopLoss)}</p>
              <p className="text-[10px] text-red-400/70 mt-0.5">
                {((stopLoss - entryPrice) / entryPrice * 100).toFixed(2)}%
              </p>
            </div>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* TP1 */}
        <div className="text-center">
          {signal.tp1 && entryPrice > 0 ? (
            <div>
              <p className="font-mono text-sm text-emerald-400/90">{formatPrice(signal.tp1)}</p>
              <p className="text-[10px] text-emerald-400/70 mt-0.5">
                {((signal.tp1 - entryPrice) / entryPrice * 100).toFixed(2)}%
              </p>
            </div>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* TP2 */}
        <div className="text-center">
          {signal.tp2 && entryPrice > 0 ? (
            <div>
              <p className="font-mono text-sm text-emerald-500/90">{formatPrice(signal.tp2)}</p>
              <p className="text-[10px] text-emerald-500/70 mt-0.5">
                {((signal.tp2 - entryPrice) / entryPrice * 100).toFixed(2)}%
              </p>
            </div>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* TP3 */}
        <div className="text-center">
          {signal.tp3 && entryPrice > 0 ? (
            <div>
              <p className="font-mono text-sm text-emerald-600/90">{formatPrice(signal.tp3)}</p>
              <p className="text-[10px] text-emerald-600/70 mt-0.5">
                {((signal.tp3 - entryPrice) / entryPrice * 100).toFixed(2)}%
              </p>
            </div>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* Swing High */}
        <div className="text-center">
          {swingHigh !== null ? (
            <div>
              <p className="font-mono text-sm text-emerald-400/90">{formatPrice(swingHigh)}</p>
              {swingHighTimeDelta && (
                <p className="text-[10px] font-medium text-muted-foreground/80 mt-0.5" title={swingHighTimestamp || undefined}>
                  {swingHighTimeDelta}
                </p>
              )}
              {swingHighTimestamp && (
                <p className="text-[9px] text-muted-foreground/60 mt-0.5">{swingHighTimestamp}</p>
              )}
            </div>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* Swing Low */}
        <div className="text-center">
          {swingLow !== null ? (
            <div>
              <p className="font-mono text-sm text-red-400/90">{formatPrice(swingLow)}</p>
              {swingLowTimeDelta && (
                <p className="text-[10px] font-medium text-muted-foreground/80 mt-0.5" title={swingLowTimestamp || undefined}>
                  {swingLowTimeDelta}
                </p>
              )}
              {swingLowTimestamp && (
                <p className="text-[9px] text-muted-foreground/60 mt-0.5">{swingLowTimestamp}</p>
              )}
            </div>
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* Confluence */}
        <div>
          {signal.confluence ? (
            <ConfluenceBadges 
              confluence={signal.confluence} 
              confluenceValue={typeof signal.confluence === "string" 
                ? parseInt(signal.confluence, 10) 
                : undefined} 
            />
          ) : (
            <span className="text-muted-foreground/60 text-xs">-</span>
          )}
        </div>

        {/* Timestamp */}
        <div className="text-center">
          <p className="text-xs text-muted-foreground/80">{lastUpdated}</p>
        </div>

        {/* Action Button */}
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={handleViewChart}
            className="h-8 px-3"
            aria-label={`View chart for ${signal.symbol}`}
          >
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    );
  },
  (prev, next) => {
    // Custom comparison for better memoization
    if (prev.signal.id !== next.signal.id) return false;
    if (prev.signal.timestamp !== next.signal.timestamp) return false;
    if (prev.signal.swing_high_timestamp !== next.signal.swing_high_timestamp) return false;
    if (prev.signal.swing_low_timestamp !== next.signal.swing_low_timestamp) return false;
    if (prev.currentPrice !== next.currentPrice) return false;
    return true;
  }
);

SignalRow.displayName = "SignalRow";
