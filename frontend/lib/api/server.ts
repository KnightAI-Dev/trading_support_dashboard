/**
 * Server-side API calls with Next.js caching
 * Use this in Server Components and Route Handlers
 */
import { Candle, TradingSignal, MarketMetadata, SymbolDetails } from "./types";
import type { SymbolItem } from "@/components/ui/SymbolManager";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FetchOptions {
  next?: {
    revalidate?: number;
    tags?: string[];
  };
  cache?: RequestCache;
}

type ExtendedFetchOptions = RequestInit & {
  next?: {
    revalidate?: number;
    tags?: string[];
  };
};

function buildFetchOptions(
  defaultRevalidate: number,
  options?: FetchOptions
): ExtendedFetchOptions {
  const fetchOptions: ExtendedFetchOptions = {};

  if (options?.cache) {
    fetchOptions.cache = options.cache;
    return fetchOptions;
  }

  fetchOptions.next = options?.next ?? { revalidate: defaultRevalidate };
  return fetchOptions;
}

// Helper to map alert to signal
function mapAlertToSignal(alert: any): TradingSignal {
  return {
    id: alert.id,
    symbol: alert.symbol,
    timeframe: alert.timeframe,
    timestamp: alert.timestamp,
    market_score: 0,
    direction: alert.direction || "long",
    price: alert.entry_price,
    entry1: alert.entry_price,
    entry2: undefined,
    sl: alert.stop_loss,
    tp1: alert.take_profit_1,
    tp2: alert.take_profit_2,
    tp3: alert.take_profit_3,
    swing_high: alert.swing_high_price,
    swing_high_timestamp: alert.swing_high_timestamp,
    swing_low: alert.swing_low_price,
    swing_low_timestamp: alert.swing_low_timestamp,
    support_level: undefined,
    resistance_level: undefined,
    confluence: alert.risk_score,
    risk_reward_ratio: undefined,
    pullback_detected: false,
    confidence_score: undefined,
  };
}

export async function fetchSignals(
  params?: {
    symbol?: string;
    timeframe?: string;
    direction?: string;
    limit?: number;
  },
  options?: FetchOptions
): Promise<TradingSignal[]> {
  const queryParams = new URLSearchParams();
  if (params?.symbol) queryParams.append("symbol", params.symbol);
  if (params?.timeframe) queryParams.append("timeframe", params.timeframe);
  if (params?.direction) queryParams.append("direction", params.direction);
  if (params?.limit) queryParams.append("limit", params.limit.toString());

  const response = await fetch(
    `${API_URL}/alerts?${queryParams}`,
    buildFetchOptions(30, options)
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch alerts: ${response.statusText}`);
  }

  const alerts = await response.json();
  return alerts.map(mapAlertToSignal);
}

export async function fetchLatestSignal(
  symbol: string,
  timeframe?: string,
  options?: FetchOptions
): Promise<TradingSignal | null> {
  try {
    const url = timeframe
      ? `${API_URL}/alerts/${symbol}/latest?timeframe=${timeframe}`
      : `${API_URL}/alerts/${symbol}/latest`;

    const response = await fetch(url, buildFetchOptions(30, options));

    if (response.status === 404) return null;
    if (!response.ok) {
      throw new Error(`Failed to fetch latest alert: ${response.statusText}`);
    }

    const alert = await response.json();
    return mapAlertToSignal(alert);
  } catch (error) {
    console.error("Error fetching latest signal:", error);
    return null;
  }
}

export async function fetchAlertsForSwings(
  symbol: string,
  timeframe: string,
  limit: number = 100,
  options?: FetchOptions
): Promise<TradingSignal[]> {
  const queryParams = new URLSearchParams({
    timeframe,
    limit: limit.toString(),
  });

  const response = await fetch(
    `${API_URL}/alerts/${symbol}/swings?${queryParams}`,
    buildFetchOptions(60, options)
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch alerts for swings: ${response.statusText}`);
  }

  const alerts = await response.json();
  return alerts.map(mapAlertToSignal);
}

export async function fetchCandles(
  symbol: string,
  timeframe: string = "1h",
  limit: number = 100,
  before?: string,
  options?: FetchOptions
): Promise<Candle[]> {
  const params = new URLSearchParams({
    timeframe,
    limit: limit.toString(),
  });
  if (before) {
    params.append("before", before);
  }

  const response = await fetch(
    `${API_URL}/candles/${symbol}?${params}`,
    buildFetchOptions(60, options)
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch candles: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchMarketMetadata(
  options?: FetchOptions
): Promise<MarketMetadata> {
  const response = await fetch(
    `${API_URL}/metadata/market`,
    buildFetchOptions(300, options)
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch market metadata: ${response.statusText}`);
  }

  const data = await response.json();

  const symbolTimeframes: Record<string, string[]> = {};
  if (data.symbol_timeframes && typeof data.symbol_timeframes === "object") {
    Object.entries(data.symbol_timeframes as Record<string, string[]>).forEach(
      ([symbol, timeframes]) => {
        symbolTimeframes[symbol] = Array.isArray(timeframes) ? timeframes : [];
      }
    );
  }

  if (!Object.keys(symbolTimeframes).length && Array.isArray(data.symbols)) {
    data.symbols.forEach((symbol: string) => {
      symbolTimeframes[symbol] = Array.isArray(data.timeframes) ? data.timeframes : [];
    });
  }

  return {
    symbols: (data.symbols || []) as string[],
    timeframes: (data.timeframes || []) as string[],
    symbolTimeframes,
  };
}

export async function fetchSymbolDetails(
  symbol: string,
  options?: FetchOptions
): Promise<SymbolDetails> {
  const response = await fetch(
    `${API_URL}/symbols/${symbol}/details`,
    buildFetchOptions(60, options)
  );

  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Symbol ${symbol} not found`);
    }
    throw new Error(`Failed to fetch symbol details: ${response.statusText}`);
  }

  return response.json();
}

export async function fetchSymbolsWithPrices(
  options?: FetchOptions
): Promise<SymbolItem[]> {
  const response = await fetch(
    `${API_URL}/symbols`,
    buildFetchOptions(30, options)
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch symbols: ${response.statusText}`);
  }

  return response.json();
}

