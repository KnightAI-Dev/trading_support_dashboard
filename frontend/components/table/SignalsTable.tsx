"use client";

import { useState, useMemo, useEffect } from "react";
import { TradingSignal } from "@/lib/api";
import { ConfluenceBadges } from "@/components/ui/ConfluenceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatPrice, formatTimestamp } from "@/lib/utils";
import { TrendingUp, TrendingDown, ArrowUpDown, ArrowUp, ArrowDown, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useMarketStore } from "@/stores/useMarketStore";
import { subscribeToSymbolUpdates } from "@/hooks/useSymbolData";
import { SymbolItem } from "@/components/ui/SymbolManager";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type SortField = 
  | "timestamp" 
  | "market_score" 
  | "symbol" 
  | "timeframe"
  | "direction" 
  | "entry"
  | "sl"
  | "tp1"
  | "price"
  | "price_score";
type SortDirection = "asc" | "desc";

interface SignalsTableProps {
  signals: TradingSignal[];
  onRowClick?: (signal: TradingSignal) => void;
}

export function SignalsTable({ signals, onRowClick }: SignalsTableProps) {
  const router = useRouter();
  const { setSelectedSymbol, setSelectedTimeframe, setLatestSignal } = useMarketStore();
  const [sortField, setSortField] = useState<SortField>("price_score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  
  // State to store current prices for each symbol (from WebSocket updates)
  const [symbolPrices, setSymbolPrices] = useState<Record<string, number>>({});

  // Subscribe to WebSocket symbol price updates
  useEffect(() => {
    const unsubscribe = subscribeToSymbolUpdates((update: Partial<SymbolItem>) => {
      if (update.symbol && update.price !== undefined) {
        setSymbolPrices((prev) => ({
          ...prev,
          [update.symbol!]: update.price!,
        }));
      }
    });

    return unsubscribe;
  }, []);

  // Fetch initial prices from API on mount
  useEffect(() => {
    const fetchInitialPrices = async () => {
      try {
        const response = await fetch(`${API_URL}/symbols`);
        if (response.ok) {
          const symbols: SymbolItem[] = await response.json();
          const prices: Record<string, number> = {};
          symbols.forEach((symbol) => {
            if (symbol.price !== undefined && symbol.price !== null) {
              prices[symbol.symbol] = symbol.price;
            }
          });
          setSymbolPrices((prev) => ({ ...prev, ...prices }));
        }
      } catch (error) {
        console.error("Error fetching initial prices:", error);
      }
    };

    fetchInitialPrices();
  }, []);

  const sortedSignals = useMemo(() => {
    const sorted = [...signals].sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortField) {
        case "timestamp":
          aValue = new Date(a.timestamp).getTime();
          bValue = new Date(b.timestamp).getTime();
          break;
        case "market_score":
          aValue = a.market_score || 0;
          bValue = b.market_score || 0;
          break;
        case "symbol":
          aValue = a.symbol;
          bValue = b.symbol;
          break;
        case "timeframe":
          aValue = a.timeframe || "";
          bValue = b.timeframe || "";
          break;
        case "direction":
          aValue = a.direction;
          bValue = b.direction;
          break;
        case "entry":
          aValue = a.entry1 || a.price || 0;
          bValue = b.entry1 || b.price || 0;
          break;
        case "sl":
          aValue = a.sl || 0;
          bValue = b.sl || 0;
          break;
        case "tp1":
          aValue = a.tp1 || 0;
          bValue = b.tp1 || 0;
          break;
        case "price":
          aValue = symbolPrices[a.symbol] || 0;
          bValue = symbolPrices[b.symbol] || 0;
          break;
        case "price_score":
          // Calculate score: abs(current_price - entry_price) / entry_price
          const aEntryPrice = a.entry1 || a.price || 0;
          const aCurrentPrice = symbolPrices[a.symbol] || 0;
          const bEntryPrice = b.entry1 || b.price || 0;
          const bCurrentPrice = symbolPrices[b.symbol] || 0;
          aValue = aEntryPrice > 0 ? Math.abs(aCurrentPrice - aEntryPrice) / aEntryPrice : 0;
          bValue = bEntryPrice > 0 ? Math.abs(bCurrentPrice - bEntryPrice) / bEntryPrice : 0;
          break;
        default:
          return 0;
      }

      if (typeof aValue === "string" && typeof bValue === "string") {
        return sortDirection === "asc"
          ? aValue.localeCompare(bValue)
          : bValue.localeCompare(aValue);
      }

      return sortDirection === "asc" 
        ? (aValue as number) - (bValue as number)
        : (bValue as number) - (aValue as number);
    });

    return sorted;
  }, [signals, sortField, sortDirection, symbolPrices]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const handleRowClick = (signal: TradingSignal) => {
    setSelectedSymbol(signal.symbol);
    setLatestSignal(signal);
    if (onRowClick) {
      onRowClick(signal);
    } else {
      router.push(`/dashboard`);
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-3 w-3 ml-1 opacity-50" />;
    }
    return sortDirection === "asc" 
      ? <ArrowUp className="h-3 w-3 ml-1" />
      : <ArrowDown className="h-3 w-3 ml-1" />;
  };

  if (signals.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No signals available</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="px-4 py-3 text-left">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold"
                  onClick={() => handleSort("symbol")}
                >
                  Symbol
                  <SortIcon field="symbol" />
                </Button>
              </th>
              <th className="px-4 py-3 text-left">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold"
                  onClick={() => handleSort("timeframe")}
                >
                  Timeframe
                  <SortIcon field="timeframe" />
                </Button>
              </th>
              <th className="px-4 py-3 text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold"
                  onClick={() => handleSort("price")}
                >
                  Price
                  <SortIcon field="price" />
                </Button>
              </th>
              <th className="px-4 py-3 text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold"
                  onClick={() => handleSort("price_score")}
                >
                  Price Score
                  <SortIcon field="price_score" />
                </Button>
              </th>
              <th className="px-4 py-3 text-left">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold"
                  onClick={() => handleSort("direction")}
                >
                  Direction
                  <SortIcon field="direction" />
                </Button>
              </th>
              <th className="px-4 py-3 text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold"
                  onClick={() => handleSort("entry")}
                >
                  Entry
                  <SortIcon field="entry" />
                </Button>
              </th>
              <th className="px-4 py-3 text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold"
                  onClick={() => handleSort("sl")}
                >
                  SL
                  <SortIcon field="sl" />
                </Button>
              </th>
              <th className="px-4 py-3 text-right">TP1</th>
              <th className="px-4 py-3 text-right">TP2</th>
              <th className="px-4 py-3 text-right">TP3</th>
              <th className="px-4 py-3 text-right">Swing High</th>
              <th className="px-4 py-3 text-right">Swing Low</th>
              <th className="px-4 py-3 text-left">Confluence</th>
              <th className="px-4 py-3 text-left">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-auto p-0 font-semibold"
                  onClick={() => handleSort("timestamp")}
                >
                  Timestamp
                  <SortIcon field="timestamp" />
                </Button>
              </th>
              <th className="px-4 py-3 text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            {sortedSignals.map((signal, index) => {
              const isHighScore = (signal.market_score || 0) >= 90;
              const currentPrice = symbolPrices[signal.symbol]; // Get current price for this symbol
              
              return (
                <motion.tr
                  key={signal.id || index}
                  className={`
                    border-b transition-colors hover:bg-muted/50 cursor-pointer
                    ${isHighScore ? "bg-emerald-500/10" : ""}
                    ${signal.direction === "long" ? "hover:bg-green-500/5" : "hover:bg-red-500/5"}
                  `}
                  // onClick={() => handleRowClick(signal)}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.02 }}
                >
                  <td className="px-4 py-3 font-medium">
                    {signal.symbol.replace("USDT", "/USDT")}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {signal.timeframe || "-"}
                  </td>
                  <td className="px-4 py-3 text-right font-medium">
                    {currentPrice !== undefined && currentPrice !== null 
                      ? formatPrice(currentPrice) 
                      : <span className="text-muted-foreground">-</span>
                    }
                  </td>
                  <td className="px-4 py-3 text-right">
                    {(() => {
                      const entryPrice = signal.entry1 || signal.price || 0;
                      let priceScore: number | null = null;
                      
                      if (currentPrice !== undefined && currentPrice !== null && entryPrice > 0) {
                        // Calculate: abs(current_price - entry_price) / entry_price
                        priceScore = Math.abs(currentPrice - entryPrice) / entryPrice;
                      }
                      
                      if (priceScore !== null) {
                        // Display as percentage with 2 decimal places
                        const percentage = (priceScore * 100).toFixed(2);
                        // Color coding: green if close to entry (< 1%), yellow if moderate (1-3%), red if far (> 3%)
                        const colorClass = priceScore < 0.01 
                          ? "text-green-400" 
                          : priceScore < 0.03 
                          ? "text-yellow-400" 
                          : "text-red-400";
                        
                        return (
                          <span className={`font-medium ${colorClass}`}>
                            {percentage}%
                          </span>
                        );
                      }
                      
                      return <span className="text-muted-foreground">-</span>;
                    })()}
                  </td>
                  <td className="px-4 py-3">
                    <Badge
                      variant={signal.direction === "long" ? "long" : "short"}
                      className="flex items-center gap-1 w-fit"
                    >
                      {signal.direction === "long" ? (
                        <TrendingUp className="h-3 w-3" />
                      ) : (
                        <TrendingDown className="h-3 w-3" />
                      )}
                      {signal.direction.toUpperCase()}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-medium">
                    <div className="flex flex-col items-end gap-1">
                      <span>{formatPrice(signal.entry1 || signal.price)}</span>
                      {signal.sl && (signal.entry1 || signal.price) && (
                        <span className="text-xs text-muted-foreground">
                          {(() => {
                            const entry = signal.entry1 || signal.price || 0;
                            const sl = signal.sl;
                            const diff = Math.abs(entry - sl);
                            const diffPercent = entry > 0 ? ((diff / entry) * 100).toFixed(2) : "0.00";
                            return `${formatPrice(diff)} (${diffPercent}%)`;
                          })()}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right text-red-400">
                    {signal.sl ? formatPrice(signal.sl) : "-"}
                  </td>
                  <td className="px-4 py-3 text-right text-green-400">
                    {signal.tp1 ? formatPrice(signal.tp1) : "-"}
                  </td>
                  <td className="px-4 py-3 text-right text-green-400">
                    {signal.tp2 ? formatPrice(signal.tp2) : "-"}
                  </td>
                  <td className="px-4 py-3 text-right text-green-400">
                    {signal.tp3 ? formatPrice(signal.tp3) : "-"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {signal.swing_high ? (
                      <div className="flex flex-col items-end gap-1">
                        <span className="font-medium">{formatPrice(signal.swing_high)}</span>
                        {signal.swing_high_timestamp && (
                          <span className="text-xs text-muted-foreground">
                            {formatTimestamp(signal.swing_high_timestamp)}
                          </span>
                        )}
                      </div>
                    ) : "-"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {signal.swing_low ? (
                      <div className="flex flex-col items-end gap-1">
                        <span className="font-medium">{formatPrice(signal.swing_low)}</span>
                        {signal.swing_low_timestamp && (
                          <span className="text-xs text-muted-foreground">
                            {formatTimestamp(signal.swing_low_timestamp)}
                          </span>
                        )}
                      </div>
                    ) : "-"}
                  </td>
                  <td className="px-4 py-3">
                    {signal.confluence ? (
                      <ConfluenceBadges confluence={signal.confluence} />
                    ) : (
                      <span className="text-muted-foreground text-sm">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {formatTimestamp(signal.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={async (e) => {
                        e.stopPropagation(); // Prevent row click
                        try {
                          // Set symbol and timeframe first
                          setSelectedSymbol(signal.symbol as any);
                          if (signal.timeframe) {
                            setSelectedTimeframe(signal.timeframe as any);
                          }
                          // Store the signal in sessionStorage as backup
                          sessionStorage.setItem('presetSignal', JSON.stringify(signal));
                          // Set the signal in store
                          setLatestSignal(signal);
                          // Small delay to ensure state updates propagate
                          await new Promise(resolve => setTimeout(resolve, 50));
                          // Navigate to dashboard
                          router.push("/dashboard");
                        } catch (error) {
                          console.error("Error navigating to dashboard:", error);
                        }
                      }}
                      className="h-7 px-3"
                      title="Go to dashboard with this signal"
                    >
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

