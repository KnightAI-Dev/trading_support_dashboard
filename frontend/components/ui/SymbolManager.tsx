"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { Search, X, Filter } from "lucide-react";
import { useMarketStore } from "@/stores/useMarketStore";
import { useDebounce } from "@/hooks/useDebounce";
import { SymbolRow } from "./SymbolRow";
import { FavoritesSection } from "./FavoritesSection";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

export interface SymbolItem {
  symbol: string;
  base: string;
  quote: string;
  marketcap?: number;
  volume_24h?: number;
  price: number;
  change24h: number;
}

interface SymbolManagerProps {
  symbols: SymbolItem[];
  onSelect?: (symbol: string) => void;
  onFavoriteChange?: (favorites: string[]) => void;
  className?: string;
}

const FAVORITES_STORAGE_KEY = "trading_dashboard_favorites";

export function SymbolManager({
  symbols,
  onSelect,
  onFavoriteChange,
  className = "",
}: SymbolManagerProps) {
  const { selectedSymbol, setSelectedSymbol } = useMarketStore();
  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearchQuery = useDebounce(searchQuery, 150);
  const [showFilters, setShowFilters] = useState(false);
  const [minMarketCap, setMinMarketCap] = useState("");
  const [maxMarketCap, setMaxMarketCap] = useState("");
  const [minVolume24h, setMinVolume24h] = useState("");
  const [maxVolume24h, setMaxVolume24h] = useState("");
  const [favorites, setFavorites] = useState<string[]>(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem(FAVORITES_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    }
    return [];
  });

  // Persist favorites to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(favorites));
      onFavoriteChange?.(favorites);
    }
  }, [favorites, onFavoriteChange]);

  // Filter symbols based on search query and filters
  const filteredSymbols = useMemo(() => {
    let filtered = symbols;

    // Apply search filter
    if (debouncedSearchQuery.trim()) {
      const query = debouncedSearchQuery.toLowerCase().trim();
      filtered = filtered.filter(
        (item) =>
          item.symbol.toLowerCase().includes(query) ||
          item.base.toLowerCase().includes(query) ||
          item.quote.toLowerCase().includes(query)
      );
    }

    // Apply market cap filters
    if (minMarketCap) {
      const min = parseFloat(minMarketCap);
      if (!isNaN(min)) {
        filtered = filtered.filter(
          (item) => (item.marketcap || 0) >= min
        );
      }
    }
    if (maxMarketCap) {
      const max = parseFloat(maxMarketCap);
      if (!isNaN(max)) {
        filtered = filtered.filter(
          (item) => (item.marketcap || 0) <= max
        );
      }
    }

    // Apply volume_24h filters
    if (minVolume24h) {
      const min = parseFloat(minVolume24h);
      if (!isNaN(min)) {
        filtered = filtered.filter(
          (item) => (item.volume_24h || 0) >= min
        );
      }
    }
    if (maxVolume24h) {
      const max = parseFloat(maxVolume24h);
      if (!isNaN(max)) {
        filtered = filtered.filter(
          (item) => (item.volume_24h || 0) <= max
        );
      }
    }

    return filtered;
  }, [symbols, debouncedSearchQuery, minMarketCap, maxMarketCap, minVolume24h, maxVolume24h]);

  // Separate favorites and regular symbols, sort regular by market cap
  const { favoriteItems, regularItems } = useMemo(() => {
    const favoriteSet = new Set(favorites);
    const favs: SymbolItem[] = [];
    const regular: SymbolItem[] = [];

    filteredSymbols.forEach((item) => {
      if (favoriteSet.has(item.symbol)) {
        // Maintain favorites order
        const index = favorites.indexOf(item.symbol);
        favs[index] = item;
      } else {
        regular.push(item);
      }
    });

    // Sort regular items by market cap (descending - highest first)
    // Symbols without market cap go to the end
    regular.sort((a, b) => {
      const marketCapA = a.marketcap || 0;
      const marketCapB = b.marketcap || 0;
      return marketCapB - marketCapA;
    });

    // Remove undefined entries from favorites array
    return {
      favoriteItems: favs.filter((item) => item !== undefined),
      regularItems: regular,
    };
  }, [filteredSymbols, favorites]);

  const handleSelect = useCallback(
    (symbol: string) => {
      setSelectedSymbol(symbol as any);
      onSelect?.(symbol);
    },
    [setSelectedSymbol, onSelect]
  );

  const handleToggleFavorite = useCallback(
    (symbol: string) => {
      setFavorites((prev) => {
        if (prev.includes(symbol)) {
          return prev.filter((s) => s !== symbol);
        } else {
          return [...prev, symbol];
        }
      });
    },
    []
  );

  const handleReorderFavorites = useCallback((newOrder: string[]) => {
    setFavorites(newOrder);
  }, []);

  const handleClearSearch = useCallback(() => {
    setSearchQuery("");
  }, []);

  const handleClearFilters = useCallback(() => {
    setMinMarketCap("");
    setMaxMarketCap("");
    setMinVolume24h("");
    setMaxVolume24h("");
  }, []);

  // Calculate max values for filters
  const maxValues = useMemo(() => {
    if (symbols.length === 0) return { marketcap: 0, volume_24h: 0 };
    return {
      marketcap: Math.max(...symbols.map((s) => s.marketcap || 0)),
      volume_24h: Math.max(...symbols.map((s) => s.volume_24h || 0)),
    };
  }, [symbols]);

  const formatNumber = useCallback((num: number): string => {
    if (num >= 1e12) return `${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
    if (num >= 1e3) return `${(num / 1e3).toFixed(2)}K`;
    return num.toFixed(2);
  }, []);

  return (
    <div
      className={`flex flex-col h-full bg-background border-r border-border ${className}`}
      style={{ width: "260px" }}
    >
      {/* Search Box and Filters */}
      <div className="sticky top-0 z-10 bg-background border-b border-border">
        <div className="p-3">
          <div className="relative mb-2">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search symbols..."
              className="w-full pl-9 pr-8 py-2 bg-muted rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            {searchQuery && (
              <button
                onClick={handleClearSearch}
                className="absolute right-2 top-1/2 transform -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="w-full flex items-center justify-center gap-2 py-1.5 px-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <Filter className="h-3.5 w-3.5" />
            Filters
            {(minMarketCap || maxMarketCap || minVolume24h || maxVolume24h) && (
              <span className="ml-1 px-1.5 py-0.5 bg-primary/20 text-primary rounded text-xs">
                Active
              </span>
            )}
          </button>
        </div>

        {/* Filter Panel */}
        {showFilters && (
          <div className="px-3 pb-3 space-y-3 border-t border-border bg-muted/30">
            {/* Market Cap Filters */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold">Market Cap</Label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label htmlFor="min-marketcap" className="text-xs text-muted-foreground">
                    Min
                  </Label>
                  <Input
                    id="min-marketcap"
                    type="number"
                    placeholder="0"
                    value={minMarketCap}
                    onChange={(e) => setMinMarketCap(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div>
                  <Label htmlFor="max-marketcap" className="text-xs text-muted-foreground">
                    Max
                  </Label>
                  <Input
                    id="max-marketcap"
                    type="number"
                    placeholder={formatNumber(maxValues.marketcap)}
                    value={maxMarketCap}
                    onChange={(e) => setMaxMarketCap(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Volume 24h Filters */}
            <div className="space-y-2">
              <Label className="text-xs font-semibold">24h Volume</Label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label htmlFor="min-volume" className="text-xs text-muted-foreground">
                    Min
                  </Label>
                  <Input
                    id="min-volume"
                    type="number"
                    placeholder="0"
                    value={minVolume24h}
                    onChange={(e) => setMinVolume24h(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
                <div>
                  <Label htmlFor="max-volume" className="text-xs text-muted-foreground">
                    Max
                  </Label>
                  <Input
                    id="max-volume"
                    type="number"
                    placeholder={formatNumber(maxValues.volume_24h)}
                    value={maxVolume24h}
                    onChange={(e) => setMaxVolume24h(e.target.value)}
                    className="h-8 text-xs"
                  />
                </div>
              </div>
            </div>

            {/* Clear Filters Button */}
            {(minMarketCap || maxMarketCap || minVolume24h || maxVolume24h) && (
              <button
                onClick={handleClearFilters}
                className="w-full py-1.5 px-2 text-xs text-muted-foreground hover:text-foreground border border-border rounded hover:bg-muted transition-colors"
              >
                Clear Filters
              </button>
            )}
          </div>
        )}
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        {/* Favorites Section */}
        {favoriteItems.length > 0 && (
          <FavoritesSection
            items={favoriteItems}
            favorites={favorites}
            selectedSymbol={selectedSymbol}
            onSelect={handleSelect}
            onToggleFavorite={handleToggleFavorite}
            onReorder={handleReorderFavorites}
          />
        )}

        {/* Regular Symbols List */}
        <div className="py-2">
          {regularItems.length > 0 ? (
            regularItems.map((item) => (
              <SymbolRow
                key={item.symbol}
                item={item}
                isSelected={item.symbol === selectedSymbol}
                isFavorite={favorites.includes(item.symbol)}
                onSelect={handleSelect}
                onToggleFavorite={handleToggleFavorite}
              />
            ))
          ) : searchQuery ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              No symbols found
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

