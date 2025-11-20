"use client";

import { useEffect, useState } from "react";
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

  // Fetch symbols from backend on mount
  useEffect(() => {
    let isMounted = true;

    const loadSymbols = async () => {
      setIsLoadingSymbols(true);
      try {
        const metadata = await fetchMarketMetadata();
        if (isMounted) {
          setMarketMetadata(metadata);
        }
      } catch (error) {
        console.error("Error loading symbols from backend:", error);
      } finally {
        if (isMounted) {
          setIsLoadingSymbols(false);
        }
      }
    };

    // Always fetch from backend to get latest symbols
    loadSymbols();

    return () => {
      isMounted = false;
    };
  }, [setMarketMetadata]);

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

