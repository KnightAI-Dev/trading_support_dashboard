/**
 * Example usage of SymbolManager component
 * 
 * This file demonstrates how to integrate SymbolManager into your dashboard.
 * You can replace the existing SymbolSelector with this component.
 */

"use client";

import { SymbolManager, SymbolItem } from "./SymbolManager";
import { useSymbolData } from "@/hooks/useSymbolData";

export function SymbolManagerExample() {
  const { symbols, isLoading } = useSymbolData();

  // Or use your own data source:
  // const symbols: SymbolItem[] = [
  //   {
  //     symbol: "BTCUSDT",
  //     base: "BTC",
  //     quote: "USDT",
  //     price: 45000,
  //     change24h: 2.5,
  //     marketcap: 850000000000,
  //   },
  //   // ... more symbols
  // ];

  const handleSelect = (symbol: string) => {
    console.log("Selected symbol:", symbol);
    // Your selection logic here
  };

  const handleFavoriteChange = (favorites: string[]) => {
    console.log("Favorites changed:", favorites);
    // Your favorites logic here
  };

  if (isLoading) {
    return (
      <div className="w-[260px] h-full bg-background border-r border-border flex items-center justify-center">
        <div className="text-sm text-muted-foreground">Loading symbols...</div>
      </div>
    );
  }

  return (
    <SymbolManager
      symbols={symbols}
      onSelect={handleSelect}
      onFavoriteChange={handleFavoriteChange}
    />
  );
}

/**
 * Integration into Dashboard Layout:
 * 
 * Replace the existing SymbolSelector in your dashboard with:
 * 
 * <div className="flex h-screen">
 *   <SymbolManager
 *     symbols={symbols}
 *     onSelect={(symbol) => setSelectedSymbol(symbol)}
 *   />
 *   <div className="flex-1">
 *     {/* Your main dashboard content */}
 *   </div>
 * </div>
 */

