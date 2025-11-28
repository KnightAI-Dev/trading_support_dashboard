"use client";

import { useEffect, useMemo, useState, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { TradingSignal } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ArrowLeft,
  Filter,
  Search,
  ArrowUp,
  ArrowDown,
  Lock,
  Unlock,
  Plus,
  X,
} from "lucide-react";
import { SignalList } from "@/components/signals/SignalList";
import { useSignalsStore } from "@/stores/useSignalsStore";
import { useSignalFeed } from "@/hooks/useSignalFeed";
import { useSymbolData } from "@/hooks/useSymbolData";
import { cn } from "@/lib/utils";

interface SignalsClientProps {
  initialSignals: TradingSignal[];
}

const statusStyles: Record<string, string> = {
  connected: "bg-emerald-400",
  connecting: "bg-amber-400",
  disconnected: "bg-red-400",
  idle: "bg-muted-foreground",
};

const formatRelative = (timestamp: number | null) => {
  if (!timestamp) return "Waiting for live data";
  const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (diffSeconds < 1) return "Just now";
  if (diffSeconds < 60) return `${diffSeconds}s ago`;
  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  return `${diffHours}h ago`;
};

type SortField = "swing_timestamp" | "price_score" | "confluence" | "symbol" | "entry_price" | "timestamp";
type SortDirection = "asc" | "desc";

interface SortOption {
  field: SortField;
  direction: SortDirection;
}

const calculatePriceScore = (currentPrice: number | null | undefined, entryPrice: number): number => {
  if (!currentPrice || currentPrice <= 0 || entryPrice <= 0) return Infinity;
  return Math.abs(currentPrice - entryPrice) / currentPrice * 100;
};

// Extract sorting logic to a utility function
const getSortValue = (
  signal: TradingSignal,
  field: SortField,
  symbols: Array<{ symbol: string; price: number }>
): number | string => {
  switch (field) {
    case "swing_timestamp": {
      const highTs = signal.swing_high_timestamp ? new Date(signal.swing_high_timestamp).getTime() : 0;
      const lowTs = signal.swing_low_timestamp ? new Date(signal.swing_low_timestamp).getTime() : 0;
      return Math.max(highTs, lowTs);
    }
    case "price_score": {
      const entryPrice = signal.entry1 ?? signal.price ?? 0;
      const currentPrice = symbols.find((s) => s.symbol === signal.symbol)?.price ?? null;
      return calculatePriceScore(currentPrice, entryPrice);
    }
    case "confluence": {
      if (!signal.confluence || typeof signal.confluence !== "string") return 0;
      const value = parseInt(signal.confluence, 10);
      return isNaN(value) ? 0 : value;
    }
    case "symbol":
      return signal.symbol.toLowerCase();
    case "entry_price":
      return signal.entry1 ?? signal.price ?? 0;
    case "timestamp":
      return new Date(signal.timestamp).getTime();
    default:
      return 0;
  }
};

const sortSignals = (
  signals: string[],
  lookup: Record<string, TradingSignal>,
  sortOptions: SortOption[],
  symbols: Array<{ symbol: string; price: number }>
): string[] => {
  return [...signals].sort((aId, bId) => {
    const a = lookup[aId];
    const b = lookup[bId];
    if (!a || !b) return 0;

    for (const sortOption of sortOptions) {
      const aValue = getSortValue(a, sortOption.field, symbols);
      const bValue = getSortValue(b, sortOption.field, symbols);

      if (aValue !== bValue) {
        if (typeof aValue === "string" && typeof bValue === "string") {
          const comparison = aValue.localeCompare(bValue);
          return sortOption.direction === "asc" ? comparison : -comparison;
        } else {
          const comparison = (aValue as number) - (bValue as number);
          return sortOption.direction === "asc" ? comparison : -comparison;
        }
      }
    }

    return 0;
  });
};

export function SignalsClient({ initialSignals }: SignalsClientProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [directionFilter, setDirectionFilter] = useState<"all" | "long" | "short">("all");
  const [sortOptions, setSortOptions] = useState<SortOption[]>([
    { field: "swing_timestamp", direction: "desc" },
    { field: "price_score", direction: "asc" },
    { field: "confluence", direction: "desc" },
  ]);
  const [appliedSortOptions, setAppliedSortOptions] = useState<SortOption[]>([
    { field: "swing_timestamp", direction: "desc" },
    { field: "price_score", direction: "asc" },
    { field: "confluence", direction: "desc" },
  ]);
  const MAX_SORT_OPTIONS = 3;
  const [isFixed, setIsFixed] = useState(false);
  const [fixedOrder, setFixedOrder] = useState<string[]>([]);
  const setInitialSignals = useSignalsStore((state) => state.setInitialSignals);
  const signalIds = useSignalsStore((state) => state.signalIds);
  const { status, lastMessageAt } = useSignalFeed();
  const { symbols } = useSymbolData();

  useEffect(() => {
    setInitialSignals(initialSignals ?? []);
  }, [initialSignals, setInitialSignals]);

  // Filter signals
  const filteredIds = useMemo(() => {
    const lookup = useSignalsStore.getState().signalMap;
    const query = searchTerm.trim().toLowerCase();

    return signalIds.filter((id) => {
      const signal = lookup[id];
      if (!signal) return false;
      if (query && !signal.symbol.toLowerCase().includes(query)) return false;
      if (directionFilter !== "all" && signal.direction !== directionFilter) return false;
      return true;
    });
  }, [signalIds, searchTerm, directionFilter]);

  // Sort filtered signals
  const filteredAndSortedIds = useMemo(() => {
    const lookup = useSignalsStore.getState().signalMap;

    // If fixed, maintain the fixed order for filtered items
    if (isFixed && fixedOrder.length > 0) {
      const filteredSet = new Set(filteredIds);
      return fixedOrder.filter(id => filteredSet.has(id));
    }

    return sortSignals(filteredIds, lookup, appliedSortOptions, symbols);
  }, [filteredIds, appliedSortOptions, symbols, isFixed, fixedOrder]);

  const totalSignals = signalIds.length;

  // Calculate current order for fixing
  const calculateCurrentOrder = useMemo(() => {
    const lookup = useSignalsStore.getState().signalMap;
    return sortSignals(filteredIds, lookup, appliedSortOptions, symbols);
  }, [filteredIds, appliedSortOptions, symbols]);

  // Handlers with useCallback
  const handleApplySort = useCallback(() => {
    setAppliedSortOptions([...sortOptions]);
  }, [sortOptions]);

  const handleFixedToggle = useCallback(() => {
    if (!isFixed) {
      setFixedOrder(calculateCurrentOrder);
    } else {
      setFixedOrder([]);
    }
    setIsFixed(!isFixed);
  }, [isFixed, calculateCurrentOrder]);

  const handleSortFieldChange = useCallback((index: number, field: SortField) => {
    setSortOptions((prev) => {
      const newOptions = [...prev];
      newOptions[index].field = field;
      return newOptions;
    });
  }, []);

  const handleSortDirectionChange = useCallback((index: number, direction: SortDirection) => {
    setSortOptions((prev) => {
      const newOptions = [...prev];
      newOptions[index].direction = direction;
      return newOptions;
    });
  }, []);

  const handleRemoveSort = useCallback((index: number) => {
    setSortOptions((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleAddSort = useCallback(() => {
    setSortOptions((prev) => [...prev, { field: "swing_timestamp", direction: "desc" }]);
  }, []);

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto flex max-w-[1920px] flex-col gap-6 p-4 md:p-6 lg:p-8">
        {/* Header Section */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="flex flex-wrap items-center justify-between gap-4"
        >
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm" className="gap-2">
                <ArrowLeft className="h-4 w-4" />
                Back
              </Button>
            </Link>
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-foreground">Real-time Signals</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Showing <span className="font-semibold text-foreground">{filteredAndSortedIds.length}</span> of{" "}
                <span className="font-semibold text-foreground">{totalSignals}</span> signals
              </p>
            </div>
          </div>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.1 }}
          >
            <Card className="flex items-center gap-6 px-4 py-3 text-sm">
              <div className="flex items-center gap-2">
                <motion.span
                  className={cn(
                    "h-2.5 w-2.5 rounded-full",
                    statusStyles[status] ?? statusStyles.idle
                  )}
                  animate={{
                    opacity: status === "connected" ? [1, 0.5, 1] : 1,
                  }}
                  transition={{
                    duration: 2,
                    repeat: status === "connected" ? Infinity : 0,
                  }}
                />
                <span className="capitalize font-medium">{status}</span>
              </div>
              <div className="text-muted-foreground">
                Last update: <span className="text-foreground font-medium">{formatRelative(lastMessageAt)}</span>
              </div>
            </Card>
          </motion.div>
        </motion.div>

        {/* Filters and Controls */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
        >
          <Card className="p-4 md:p-6">
            <div className="flex flex-wrap items-center gap-4 md:gap-6">
              {/* Search */}
              <div className="min-w-[220px] flex-1">
                <Label htmlFor="search" className="sr-only">
                  Search signals
                </Label>
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="search"
                    placeholder="Search by symbol..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10 h-10"
                    aria-label="Search signals by symbol"
                  />
                </div>
              </div>

              {/* Direction Filter */}
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <Label htmlFor="direction-filter" className="text-sm font-medium">
                  Direction
                </Label>
                <Select
                  value={directionFilter}
                  onValueChange={(value) => setDirectionFilter(value as "all" | "long" | "short")}
                >
                  <SelectTrigger id="direction-filter" className="w-[120px] h-10">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="long">Long</SelectItem>
                    <SelectItem value="short">Short</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Multi-Sort Options */}
              <div className="flex items-center gap-2 flex-wrap">
                <Label className="text-sm font-medium">Sort:</Label>
                <div className="flex items-center gap-2 flex-wrap">
                  <AnimatePresence mode="popLayout">
                    {sortOptions.map((option, index) => (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.9 }}
                        transition={{ duration: 0.2 }}
                        className="flex items-center gap-1.5 border rounded-lg px-2.5 py-1.5 bg-card shadow-sm"
                      >
                        <span className="text-xs text-muted-foreground font-medium">{index + 1}.</span>
                        <Select
                          value={option.field}
                          onValueChange={(value) => handleSortFieldChange(index, value as SortField)}
                          disabled={isFixed}
                        >
                          <SelectTrigger className="w-[140px] h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="swing_timestamp">Swing Timestamp</SelectItem>
                            <SelectItem value="price_score">Price Score</SelectItem>
                            <SelectItem value="confluence">Confluence</SelectItem>
                            <SelectItem value="symbol">Symbol</SelectItem>
                            <SelectItem value="entry_price">Entry Price</SelectItem>
                            <SelectItem value="timestamp">Signal Timestamp</SelectItem>
                          </SelectContent>
                        </Select>
                        <Select
                          value={option.direction}
                          onValueChange={(value) => handleSortDirectionChange(index, value as SortDirection)}
                          disabled={isFixed}
                        >
                          <SelectTrigger className="w-[80px] h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="asc">
                              <div className="flex items-center gap-1.5">
                                <ArrowUp className="h-3 w-3" />
                                <span>Asc</span>
                              </div>
                            </SelectItem>
                            <SelectItem value="desc">
                              <div className="flex items-center gap-1.5">
                                <ArrowDown className="h-3 w-3" />
                                <span>Desc</span>
                              </div>
                            </SelectItem>
                          </SelectContent>
                        </Select>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveSort(index)}
                          disabled={isFixed || sortOptions.length === 1}
                          className="h-8 w-8 p-0 hover:bg-destructive/10 hover:text-destructive"
                          aria-label={`Remove sort option ${index + 1}`}
                        >
                          <X className="h-3.5 w-3.5" />
                        </Button>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleAddSort}
                    disabled={isFixed || sortOptions.length >= MAX_SORT_OPTIONS}
                    className="h-8 gap-1.5"
                    aria-label="Add sort option"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    <span className="text-xs">Add</span>
                  </Button>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={handleApplySort}
                    disabled={isFixed}
                    className="h-8 gap-1.5 font-medium"
                    aria-label="Apply sort options"
                  >
                    Apply
                  </Button>
                </div>
              </div>

              {/* Fixed Toggle */}
              <div className="flex items-center gap-2">
                <Button
                  variant={isFixed ? "default" : "outline"}
                  size="sm"
                  onClick={handleFixedToggle}
                  className="gap-2 h-10"
                  aria-label={isFixed ? "Unlock signal order" : "Lock signal order"}
                >
                  {isFixed ? (
                    <>
                      <Lock className="h-4 w-4" />
                      <span>Fixed</span>
                    </>
                  ) : (
                    <>
                      <Unlock className="h-4 w-4" />
                      <span>Unfixed</span>
                    </>
                  )}
                </Button>
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Signal List */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.2 }}
        >
          <SignalList signalIds={filteredAndSortedIds} symbols={symbols} />
        </motion.div>
      </div>
    </div>
  );
}
