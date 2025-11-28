/**
 * Server-side API calls with Next.js caching
 * Use this in Server Components and Route Handlers
 */
import {
  Candle,
  TradingSignal,
  MarketMetadata,
  SymbolDetails,
} from "./types";
import type { SymbolItem } from "@/components/ui/SymbolManager";
import {
  mapAlertRecordToSignal,
  mapSignalResponseToSignal,
} from "./normalizeSignal";

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

  // Disable caching for large requests (>1000 signals) to avoid 2MB cache limit
  const isLargeRequest = (params?.limit ?? 0) > 1000;
  const fetchOptions = isLargeRequest 
    ? { cache: 'no-store' as RequestCache } 
    : buildFetchOptions(30, options);

  const signalsResponse = await fetch(
    `${API_URL}/signals?${queryParams}`,
    fetchOptions
  );

  if (signalsResponse.ok) {
    const signals = await signalsResponse.json();
    return signals.map(mapSignalResponseToSignal);
  }

  const fallbackResponse = await fetch(
    `${API_URL}/alerts?${queryParams}`,
    fetchOptions
  );

  if (!fallbackResponse.ok) {
    throw new Error(`Failed to fetch alerts: ${fallbackResponse.statusText}`);
  }

  const alerts = await fallbackResponse.json();
  return alerts.map(mapAlertRecordToSignal);
}

export async function fetchLatestSignal(
  symbol: string,
  timeframe?: string,
  options?: FetchOptions
): Promise<TradingSignal | null> {
  try {
    const url = timeframe
      ? `${API_URL}/signals/${symbol}/latest?timeframe=${timeframe}`
      : `${API_URL}/signals/${symbol}/latest`;

    const response = await fetch(url, buildFetchOptions(30, options));

    if (response.status === 404) return null;
    if (response.ok) {
      const signal = await response.json();
      return mapSignalResponseToSignal(signal);
    }

    const fallbackUrl = timeframe
      ? `${API_URL}/alerts/${symbol}/latest?timeframe=${timeframe}`
      : `${API_URL}/alerts/${symbol}/latest`;

    const fallback = await fetch(fallbackUrl, buildFetchOptions(30, options));

    if (fallback.status === 404) return null;
    if (!fallback.ok) {
      throw new Error(`Failed to fetch latest alert: ${fallback.statusText}`);
    }

    const alert = await fallback.json();
    return mapAlertRecordToSignal(alert);
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
  return alerts.map(mapAlertRecordToSignal);
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

