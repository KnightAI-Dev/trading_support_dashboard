"use client";

import { useEffect, useState, useCallback } from "react";
import { useMarketStore } from "@/stores/useMarketStore";
import { fetchMarketMetadata } from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function SymbolSelector() {
  const { 
    selectedSymbol, 
    setSelectedSymbol, 
    availableSymbols,
    setMarketMetadata,
    isLoading 
  } = useMarketStore();
  
  const [isLoadingSymbols, setIsLoadingSymbols] = useState(false);

  const loadSymbols = useCallback(async () => {
    setIsLoadingSymbols(true);
    try {
      const metadata = await fetchMarketMetadata();
      setMarketMetadata(metadata);
    } catch (error) {
      console.error("Error loading symbols from backend:", error);
    } finally {
      setIsLoadingSymbols(false);
    }
  }, [setMarketMetadata]);

  // Fetch symbols from backend on mount
  useEffect(() => {
    let isMounted = true;

    const load = async () => {
      await loadSymbols();
    };

    // Always fetch from backend to get latest symbols
    load();

    // Listen for ingestion config updates
    const handleRefresh = () => {
      if (isMounted) {
    loadSymbols();
      }
    };

    window.addEventListener('refreshMarketData', handleRefresh);
    window.addEventListener('ingestionConfigUpdated', handleRefresh);

    return () => {
      isMounted = false;
      window.removeEventListener('refreshMarketData', handleRefresh);
      window.removeEventListener('ingestionConfigUpdated', handleRefresh);
    };
  }, [loadSymbols]);

  // Use only backend symbols - no fallback to defaults
  // Only show symbols if we have data from backend
  const symbols = availableSymbols.length > 0 ? availableSymbols : [];
  const isDisabled = symbols.length === 0 || isLoading || isLoadingSymbols;

  return (
    <Select
      value={selectedSymbol}
      onValueChange={setSelectedSymbol}
      disabled={isDisabled}
    >
      <SelectTrigger className="w-[140px]">
        <SelectValue 
          placeholder={
            isLoadingSymbols 
              ? "Loading..." 
              : symbols.length === 0 
              ? "No symbols" 
              : "Select symbol"
          } 
        />
      </SelectTrigger>
      <SelectContent>
        {symbols.map((symbol) => (
          <SelectItem key={symbol} value={symbol}>
            {symbol.replace("USDT", "/USDT")}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

