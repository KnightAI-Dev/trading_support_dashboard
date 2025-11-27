"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
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
import { ArrowLeft, Filter, Search, ArrowUpDown, ArrowUp, ArrowDown, Lock, Unlock } from "lucide-react";
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

type SortField = "name" | "price" | "score";
type SortDirection = "asc" | "desc";

const calculatePriceScore = (currentPrice: number | null | undefined, entryPrice: number): number => {
  if (!currentPrice || currentPrice <= 0 || entryPrice <= 0) return Infinity; // Put missing prices at end
  return Math.abs(currentPrice - entryPrice) / currentPrice * 100;
};

export function SignalsClient({ initialSignals }: SignalsClientProps) {
  const [searchTerm, setSearchTerm] = useState("");
  const [directionFilter, setDirectionFilter] = useState<"all" | "long" | "short">("all");
  const [minPrice, setMinPrice] = useState<number>(0);
  const [maxPrice, setMaxPrice] = useState<number>(0);
  const [sortField, setSortField] = useState<SortField>("score");
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");
  const [isFixed, setIsFixed] = useState(false);
  const [fixedOrder, setFixedOrder] = useState<string[]>([]);
  const setInitialSignals = useSignalsStore((state) => state.setInitialSignals);
  const signalIds = useSignalsStore((state) => state.signalIds);
  const revision = useSignalsStore((state) => state.revision);
  const { status, lastMessageAt } = useSignalFeed();
  const { symbols } = useSymbolData();

  useEffect(() => {
    setInitialSignals(initialSignals ?? []);
  }, [initialSignals, setInitialSignals]);

  const filteredAndSortedIds = useMemo(() => {
    const lookup = useSignalsStore.getState().signalMap;
    const query = searchTerm.trim().toLowerCase();

    // Filter signals
    const filtered = signalIds.filter((id) => {
      const signal = lookup[id];
      if (!signal) return false;
      if (query && !signal.symbol.toLowerCase().includes(query)) return false;
      if (directionFilter !== "all" && signal.direction !== directionFilter) return false;
      
      // Filter by current price range
      const currentPrice = symbols.find((s) => s.symbol === signal.symbol)?.price ?? signal.price ?? 0;
      if (minPrice > 0 && currentPrice < minPrice) return false;
      if (maxPrice > 0 && currentPrice > maxPrice) return false;
      
      return true;
    });

    // If fixed, maintain the fixed order for filtered items
    if (isFixed && fixedOrder.length > 0) {
      // Create a set for fast lookup of filtered items
      const filteredSet = new Set(filtered);
      // Return items in fixed order that are still in the filtered set
      return fixedOrder.filter(id => filteredSet.has(id));
    }

    // Sort signals
    const sorted = [...filtered].sort((aId, bId) => {
      const a = lookup[aId];
      const b = lookup[bId];
      if (!a || !b) return 0;

      let aValue: number | string;
      let bValue: number | string;

      switch (sortField) {
        case "name":
          aValue = a.symbol.toLowerCase();
          bValue = b.symbol.toLowerCase();
          break;
        case "price": {
          const aPrice = symbols.find((s) => s.symbol === a.symbol)?.price ?? a.price ?? 0;
          const bPrice = symbols.find((s) => s.symbol === b.symbol)?.price ?? b.price ?? 0;
          aValue = aPrice;
          bValue = bPrice;
          break;
        }
        case "score": {
          const aEntryPrice = a.entry1 ?? a.price ?? 0;
          const bEntryPrice = b.entry1 ?? b.price ?? 0;
          const aCurrentPrice = symbols.find((s) => s.symbol === a.symbol)?.price ?? null;
          const bCurrentPrice = symbols.find((s) => s.symbol === b.symbol)?.price ?? null;
          aValue = calculatePriceScore(aCurrentPrice, aEntryPrice);
          bValue = calculatePriceScore(bCurrentPrice, bEntryPrice);
          break;
        }
        default:
          return 0;
      }

      if (typeof aValue === "string" && typeof bValue === "string") {
        const comparison = aValue.localeCompare(bValue);
        return sortDirection === "asc" ? comparison : -comparison;
      }

      const comparison = (aValue as number) - (bValue as number);
      return sortDirection === "asc" ? comparison : -comparison;
    });

    return sorted;
  }, [signalIds, searchTerm, directionFilter, minPrice, maxPrice, revision, sortField, sortDirection, symbols, isFixed, fixedOrder]);

  const totalSignals = signalIds.length;

  // Calculate current order for fixing
  const calculateCurrentOrder = useMemo(() => {
    const lookup = useSignalsStore.getState().signalMap;
    const query = searchTerm.trim().toLowerCase();

    // Filter signals
    const filtered = signalIds.filter((id) => {
      const signal = lookup[id];
      if (!signal) return false;
      if (query && !signal.symbol.toLowerCase().includes(query)) return false;
      if (directionFilter !== "all" && signal.direction !== directionFilter) return false;
      
      const currentPrice = symbols.find((s) => s.symbol === signal.symbol)?.price ?? signal.price ?? 0;
      if (minPrice > 0 && currentPrice < minPrice) return false;
      if (maxPrice > 0 && currentPrice > maxPrice) return false;
      
      return true;
    });

    // Sort signals
    const sorted = [...filtered].sort((aId, bId) => {
      const a = lookup[aId];
      const b = lookup[bId];
      if (!a || !b) return 0;

      let aValue: number | string;
      let bValue: number | string;

      switch (sortField) {
        case "name":
          aValue = a.symbol.toLowerCase();
          bValue = b.symbol.toLowerCase();
          break;
        case "price": {
          const aPrice = symbols.find((s) => s.symbol === a.symbol)?.price ?? a.price ?? 0;
          const bPrice = symbols.find((s) => s.symbol === b.symbol)?.price ?? b.price ?? 0;
          aValue = aPrice;
          bValue = bPrice;
          break;
        }
        case "score": {
          const aEntryPrice = a.entry1 ?? a.price ?? 0;
          const bEntryPrice = b.entry1 ?? b.price ?? 0;
          const aCurrentPrice = symbols.find((s) => s.symbol === a.symbol)?.price ?? null;
          const bCurrentPrice = symbols.find((s) => s.symbol === b.symbol)?.price ?? null;
          aValue = calculatePriceScore(aCurrentPrice, aEntryPrice);
          bValue = calculatePriceScore(bCurrentPrice, bEntryPrice);
          break;
        }
        default:
          return 0;
      }

      if (typeof aValue === "string" && typeof bValue === "string") {
        const comparison = aValue.localeCompare(bValue);
        return sortDirection === "asc" ? comparison : -comparison;
      }

      const comparison = (aValue as number) - (bValue as number);
      return sortDirection === "asc" ? comparison : -comparison;
    });

    return sorted;
  }, [signalIds, searchTerm, directionFilter, minPrice, maxPrice, sortField, sortDirection, symbols]);

  // Handle fixed button toggle
  const handleFixedToggle = () => {
    if (!isFixed) {
      // When enabling fixed, capture the current order
      setFixedOrder(calculateCurrentOrder);
    } else {
      // When disabling fixed, clear the fixed order
      setFixedOrder([]);
    }
    setIsFixed(!isFixed);
  };

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      <div className="mx-auto flex max-w-[1920px] flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Real-time Signals</h1>
              <p className="text-sm text-muted-foreground">
                Rendering {filteredAndSortedIds.length} / {totalSignals} signals
              </p>
            </div>
          </div>
          <Card className="flex items-center gap-6 px-4 py-2 text-sm">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  "h-2 w-2 rounded-full",
                  statusStyles[status] ?? statusStyles.idle
                )}
              />
              <span className="capitalize">{status}</span>
            </div>
            <div className="text-muted-foreground">
              Last update: <span className="text-foreground">{formatRelative(lastMessageAt)}</span>
            </div>
          </Card>
        </div>

        <Card className="p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="min-w-[220px] flex-1">
              <Label htmlFor="search" className="sr-only">
                Search
              </Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search by symbol..."
                  value={searchTerm}
                  onChange={(event) => setSearchTerm(event.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Label className="text-sm">Direction</Label>
              <Select value={directionFilter} onValueChange={(value) => setDirectionFilter(value as any)}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="long">Long</SelectItem>
                  <SelectItem value="short">Short</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Label htmlFor="min-price" className="text-sm">Min Price</Label>
              <Input
                id="min-price"
                type="number"
                min={0}
                step="0.01"
                placeholder="0"
                value={minPrice || ""}
                onChange={(event) => setMinPrice(Number(event.target.value) || 0)}
                className="w-[120px]"
              />
            </div>

            <div className="flex items-center gap-2">
              <Label htmlFor="max-price" className="text-sm">Max Price</Label>
              <Input
                id="max-price"
                type="number"
                min={0}
                step="0.01"
                placeholder="0"
                value={maxPrice || ""}
                onChange={(event) => setMaxPrice(Number(event.target.value) || 0)}
                className="w-[120px]"
              />
            </div>

            <div className="flex items-center gap-2">
              <Label className="text-sm">Sort by</Label>
              <Select
                value={sortField}
                onValueChange={(value) => setSortField(value as SortField)}
                disabled={isFixed}
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="score">Price Score</SelectItem>
                  <SelectItem value="price">Current Price</SelectItem>
                  <SelectItem value="name">Symbol Name</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Label className="text-sm">Order</Label>
              <Select
                value={sortDirection}
                onValueChange={(value) => setSortDirection(value as SortDirection)}
                disabled={isFixed}
              >
                <SelectTrigger className="w-[100px]">
                  <div className="flex items-center gap-2">
                    <SelectValue />
                    {/* {sortDirection === "asc" ? (
                      <ArrowUp className="h-3 w-3" />
                    ) : (
                      <ArrowDown className="h-3 w-3" />
                    )} */}
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="asc">
                    <div className="flex items-center gap-2">
                      <ArrowUp className="h-3 w-3" />
                      <span>Asc</span>
                    </div>
                  </SelectItem>
                  <SelectItem value="desc">
                    <div className="flex items-center gap-2">
                      <ArrowDown className="h-3 w-3" />
                      <span>Dsc</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant={isFixed ? "default" : "outline"}
                size="sm"
                onClick={handleFixedToggle}
                className="gap-2"
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

        <SignalList signalIds={filteredAndSortedIds} symbols={symbols} />
      </div>
    </div>
  );
}

