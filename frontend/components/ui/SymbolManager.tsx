"use client";

import { useState, useMemo, useCallback, useEffect } from "react";
import { Search, X } from "lucide-react";
import { useMarketStore } from "@/stores/useMarketStore";
import { useDebounce } from "@/hooks/useDebounce";
import { SymbolRow } from "./SymbolRow";
import { FavoritesSection } from "./FavoritesSection";

export interface SymbolItem {
  symbol: string;
  base: string;
  quote: string;
  marketcap?: number;
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

  // Filter symbols based on debounced search query
  const filteredSymbols = useMemo(() => {
    if (!debouncedSearchQuery.trim()) return symbols;

    const query = debouncedSearchQuery.toLowerCase().trim();
    return symbols.filter(
      (item) =>
        item.symbol.toLowerCase().includes(query) ||
        item.base.toLowerCase().includes(query) ||
        item.quote.toLowerCase().includes(query)
    );
  }, [symbols, debouncedSearchQuery]);

  // Separate favorites and regular symbols
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

  return (
    <div
      className={`flex flex-col h-full bg-background border-r border-border ${className}`}
      style={{ width: "260px" }}
    >
      {/* Search Box */}
      <div className="sticky top-0 z-10 bg-background border-b border-border p-3">
        <div className="relative">
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

