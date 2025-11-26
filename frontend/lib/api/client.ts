/**
 * Client-side API calls
 * Use this in Client Components for mutations and real-time updates
 */
import { Candle, TradingSignal, SymbolDetails } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export async function fetchSignals(params?: {
  symbol?: string;
  timeframe?: string;
  direction?: string;
  limit?: number;
}): Promise<TradingSignal[]> {
  const queryParams = new URLSearchParams();
  if (params?.symbol) queryParams.append("symbol", params.symbol);
  if (params?.timeframe) queryParams.append("timeframe", params.timeframe);
  if (params?.direction) queryParams.append("direction", params.direction);
  if (params?.limit) queryParams.append("limit", params.limit.toString());

  const response = await fetch(`${API_URL}/alerts?${queryParams}`);
  if (!response.ok) throw new Error("Failed to fetch alerts");
  const alerts = await response.json();
  return alerts.map(mapAlertToSignal);
}

export async function fetchLatestSignal(symbol: string): Promise<TradingSignal | null> {
  try {
    const response = await fetch(`${API_URL}/alerts/${symbol}/latest`);
    if (response.status === 404) return null;
    if (!response.ok) throw new Error("Failed to fetch latest alert");
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
  limit: number = 100
): Promise<TradingSignal[]> {
  const queryParams = new URLSearchParams({
    timeframe,
    limit: limit.toString(),
  });

  const response = await fetch(`${API_URL}/alerts/${symbol}/swings?${queryParams.toString()}`);
  if (!response.ok) throw new Error("Failed to fetch alerts for swings");
  const alerts = await response.json();
  return alerts.map(mapAlertToSignal);
}

export async function fetchCandles(
  symbol: string,
  timeframe: string = "1h",
  limit: number = 100,
  before?: string
): Promise<Candle[]> {
  const params = new URLSearchParams({
    timeframe,
    limit: limit.toString(),
  });
  if (before) {
    params.append("before", before);
  }

  const response = await fetch(`${API_URL}/candles/${symbol}?${params.toString()}`);
  if (!response.ok) throw new Error("Failed to fetch candles");
  return response.json();
}

export async function fetchSymbolDetails(symbol: string): Promise<SymbolDetails> {
  const response = await fetch(`${API_URL}/symbols/${symbol}/details`);
  if (!response.ok) {
    if (response.status === 404) {
      throw new Error(`Symbol ${symbol} not found`);
    }
    throw new Error("Failed to fetch symbol details");
  }
  return response.json();
}

// Additional client-side functions
export async function fetchSwingPoints(
  symbol: string,
  timeframe: string = "1h",
  limit: number = 100
): Promise<any[]> {
  const params = new URLSearchParams({
    timeframe,
    limit: limit.toString(),
  });
  const response = await fetch(`${API_URL}/swings/${symbol}?${params.toString()}`);
  if (!response.ok) throw new Error("Failed to fetch swing points");
  return response.json();
}

export async function fetchSRLevels(
  symbol: string,
  timeframe: string = "1h"
): Promise<any[]> {
  const params = new URLSearchParams({ timeframe });
  const response = await fetch(`${API_URL}/sr-levels/${symbol}?${params.toString()}`);
  if (!response.ok) throw new Error("Failed to fetch SR levels");
  return response.json();
}

export async function fetchMarketMetadata(): Promise<any> {
  const response = await fetch(`${API_URL}/metadata/market`);
  if (!response.ok) throw new Error("Failed to fetch market metadata");
  return response.json();
}

// Re-export types
export type {
  Candle,
  TradingSignal,
  SymbolDetails,
  SwingPoint,
  SRLevel,
  MarketMetadata,
  SymbolFilter,
  SymbolFilterCheck,
} from "../api";

