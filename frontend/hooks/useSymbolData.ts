import { useState, useEffect, useCallback, useRef } from "react";
import { SymbolItem } from "@/components/ui/SymbolManager";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Global callback registry for symbol updates
let symbolUpdateCallbacks: Set<(update: Partial<SymbolItem>) => void> = new Set();

export function subscribeToSymbolUpdates(callback: (update: Partial<SymbolItem>) => void) {
  symbolUpdateCallbacks.add(callback);
  return () => {
    symbolUpdateCallbacks.delete(callback);
  };
}

export function notifySymbolUpdate(update: Partial<SymbolItem>) {
  symbolUpdateCallbacks.forEach(callback => {
    try {
      callback(update);
    } catch (error) {
      console.error("Error in symbol update callback:", error);
    }
  });
}

/**
 * Hook to fetch and manage symbol data with prices
 * Falls back to mock data if API is unavailable
 */
export function useSymbolData() {
  const [symbols, setSymbols] = useState<SymbolItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Mock data generator for fallback
  const generateMockData = useCallback((): SymbolItem[] => {
    const mockSymbols = [
      "BTCUSDT",
      "ETHUSDT",
      "SOLUSDT",
      "BNBUSDT",
      "ADAUSDT",
      "XRPUSDT",
      "DOGEUSDT",
      "DOTUSDT",
      "MATICUSDT",
      "AVAXUSDT",
      "LINKUSDT",
      "UNIUSDT",
      "LTCUSDT",
      "ATOMUSDT",
      "ETCUSDT",
    ];

    return mockSymbols.map((symbol) => {
      const base = symbol.replace("USDT", "");
      const basePrice = Math.random() * 100000 + 1000; // Random price between 1000-101000
      const change24h = (Math.random() - 0.5) * 20; // Random change between -10% and +10%

      return {
        symbol,
        base,
        quote: "USDT",
        marketcap: Math.random() * 1000000000000,
        volume_24h: Math.random() * 50000000000,
        price: basePrice,
        change24h,
      };
    });
  }, []);

  const fetchSymbolData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/symbols`);
      
      if (!response.ok) {
        throw new Error(`API returned ${response.status}`);
      }
      
      const data = await response.json();
      
      // Ensure data is in correct format
      if (Array.isArray(data) && data.length > 0) {
        setSymbols(data);
      } else {
        // If API returns empty array, use mock data
        console.log("API returned empty symbols, using mock data");
        setSymbols(generateMockData());
        setError("No symbols available from API");
      }
    } catch (err) {
      // Fall back to mock data on error
      console.warn("Error fetching symbols from API, using mock data:", err);
      setSymbols(generateMockData());
      setError("Using mock data - API unavailable");
    } finally {
      setIsLoading(false);
    }
  }, [generateMockData]);

  useEffect(() => {
    fetchSymbolData();
  }, [fetchSymbolData]);

  // Listen for ingestion config updates to refresh symbol data
  useEffect(() => {
    const handleRefresh = () => {
      fetchSymbolData();
    };

    window.addEventListener('refreshMarketData', handleRefresh);
    window.addEventListener('ingestionConfigUpdated', handleRefresh);

    return () => {
      window.removeEventListener('refreshMarketData', handleRefresh);
      window.removeEventListener('ingestionConfigUpdated', handleRefresh);
    };
  }, [fetchSymbolData]);

  // Subscribe to WebSocket symbol updates
  useEffect(() => {
    const unsubscribe = subscribeToSymbolUpdates((update) => {
      // Update symbol data when WebSocket receives an update
      setSymbols((prevSymbols) => {
        const symbolIndex = prevSymbols.findIndex((s) => s.symbol === update.symbol);
        if (symbolIndex >= 0) {
          // Update existing symbol
          const updated = [...prevSymbols];
          updated[symbolIndex] = {
            ...updated[symbolIndex],
            ...update,
          };
          return updated;
        } else {
          // Symbol not in list yet, add it if it has required fields
          if (update.symbol && update.price !== undefined) {
            return [...prevSymbols, {
              symbol: update.symbol,
              base: update.base || update.symbol.replace("USDT", ""),
              quote: update.quote || "USDT",
              image_url: update.image_url ?? null,
              marketcap: update.marketcap ?? 0,
              volume_24h: update.volume_24h ?? 0,
              price: update.price,
              change24h: update.change24h ?? 0,
            }];
          }
          return prevSymbols;
        }
      });
    });

    return unsubscribe;
  }, []);

  return { symbols, isLoading, error, refetch: fetchSymbolData };
}

