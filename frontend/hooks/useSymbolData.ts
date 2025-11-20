import { useState, useEffect, useCallback } from "react";
import { SymbolItem } from "@/components/ui/SymbolManager";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

    // Optionally set up polling for live price updates
    // const interval = setInterval(() => {
    //   fetchSymbolData();
    // }, 30000); // Update every 30 seconds

    // return () => clearInterval(interval);
  }, [fetchSymbolData]);

  return { symbols, isLoading, error, refetch: fetchSymbolData };
}

