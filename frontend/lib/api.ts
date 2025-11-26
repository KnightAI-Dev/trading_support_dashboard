import { Symbol, Timeframe } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Candle {
  symbol: string;
  timeframe: string;
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SwingPoint {
  id: number;
  symbol: string;
  timeframe: string;
  type: "high" | "low";
  price: number;
  timestamp: string;
}

export interface SRLevel {
  id: number;
  symbol: string;
  timeframe: string;
  level: number;
  type: "support" | "resistance";
  strength: number;
  touches: number;
}

export interface TradingSignal {
  id: number;
  symbol: string;
  timeframe?: string;  // Add timeframe field
  timestamp: string;
  market_score: number;
  direction: "long" | "short";
  price: number;
  entry1?: number;
  entry2?: number;
  sl?: number;
  tp1?: number;
  tp2?: number;
  tp3?: number;
  swing_high?: number;
  swing_high_timestamp?: string;  // Add swing high timestamp
  swing_low?: number;
  swing_low_timestamp?: string;  // Add swing low timestamp
  support_level?: number;
  resistance_level?: number;
  confluence?: string;
  risk_reward_ratio?: number;
  pullback_detected: boolean;
  confidence_score?: number;
}

export interface SignalSummary extends TradingSignal {
  // Same as TradingSignal
}

export interface MarketMetadata {
  symbols: Symbol[];
  timeframes: Timeframe[];
  symbolTimeframes: Record<string, Timeframe[]>;
}

// Helper function to map StrategyAlert to TradingSignal
function mapAlertToSignal(alert: any): TradingSignal {
  return {
    id: alert.id,
    symbol: alert.symbol,
    timeframe: alert.timeframe,  // Include timeframe
    timestamp: alert.timestamp,
    market_score: 0, // Not available in strategy_alerts
    direction: alert.direction || "long",
    price: alert.entry_price,
    entry1: alert.entry_price,
    entry2: undefined,
    sl: alert.stop_loss,
    tp1: alert.take_profit_1,
    tp2: alert.take_profit_2,
    tp3: alert.take_profit_3,
    swing_high: alert.swing_high_price,
    swing_high_timestamp: alert.swing_high_timestamp,  // Include swing high timestamp
    swing_low: alert.swing_low_price,
    swing_low_timestamp: alert.swing_low_timestamp,  // Include swing low timestamp
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
  direction?: string;
  limit?: number;
}): Promise<TradingSignal[]> {
  const queryParams = new URLSearchParams();
  if (params?.symbol) queryParams.append("symbol", params.symbol);
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

export async function fetchSignalSummary(): Promise<SignalSummary[]> {
  const response = await fetch(`${API_URL}/alerts/summary`);
  if (!response.ok) throw new Error("Failed to fetch alert summary");
  const alerts = await response.json();
  return alerts.map(mapAlertToSignal);
}

// Strategy Configuration API
export interface StrategyConfig {
  [key: string]: string | number | object;
}

export async function fetchStrategyConfig(): Promise<StrategyConfig> {
  const response = await fetch(`${API_URL}/strategy-config`);
  if (!response.ok) throw new Error("Failed to fetch strategy config");
  return await response.json();
}

export async function updateStrategyConfig(
  configKey: string,
  configValue: string
): Promise<void> {
  const response = await fetch(`${API_URL}/strategy-config/${configKey}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config_value: configValue }),
  });
  if (!response.ok) throw new Error("Failed to update strategy config");
}

export async function updateStrategyConfigs(
  configs: Record<string, string>
): Promise<void> {
  const response = await fetch(`${API_URL}/strategy-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ configs }),
  });
  if (!response.ok) throw new Error("Failed to update strategy configs");
}

// Ingestion Configuration API
export interface IngestionConfig {
  [key: string]: string | number;
}

export async function fetchIngestionConfig(): Promise<IngestionConfig> {
  const response = await fetch(`${API_URL}/ingestion-config`);
  if (!response.ok) throw new Error("Failed to fetch ingestion config");
  return await response.json();
}

export async function updateIngestionConfig(
  configKey: string,
  configValue: string
): Promise<void> {
  const response = await fetch(`${API_URL}/ingestion-config/${configKey}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config_value: configValue }),
  });
  if (!response.ok) throw new Error("Failed to update ingestion config");
}

export async function updateIngestionConfigs(
  configs: Record<string, string>
): Promise<void> {
  const response = await fetch(`${API_URL}/ingestion-config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ configs }),
  });
  if (!response.ok) throw new Error("Failed to update ingestion configs");
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
  
  const response = await fetch(
    `${API_URL}/candles/${symbol}?${params.toString()}`
  );
  if (!response.ok) throw new Error("Failed to fetch candles");
  return response.json();
}

export async function fetchSwingPoints(
  symbol: string,
  timeframe: string = "1h"
): Promise<SwingPoint[]> {
  const response = await fetch(`${API_URL}/swings/${symbol}?timeframe=${timeframe}`);
  if (!response.ok) throw new Error("Failed to fetch swing points");
  return response.json();
}

export async function fetchSRLevels(
  symbol: string,
  timeframe: string = "1h"
): Promise<SRLevel[]> {
  const response = await fetch(`${API_URL}/sr-levels/${symbol}?timeframe=${timeframe}`);
  if (!response.ok) throw new Error("Failed to fetch S/R levels");
  return response.json();
}

export async function fetchMarketMetadata(): Promise<MarketMetadata> {
  const response = await fetch(`${API_URL}/metadata/market`);
  if (!response.ok) throw new Error("Failed to fetch market metadata");
  const data = await response.json();

  const symbolTimeframes: Record<string, Timeframe[]> = {};
  if (data.symbol_timeframes && typeof data.symbol_timeframes === "object") {
    Object.entries(data.symbol_timeframes as Record<string, Timeframe[]>).forEach(
      ([symbol, timeframes]) => {
        symbolTimeframes[symbol] = Array.isArray(timeframes)
          ? (timeframes as Timeframe[])
          : [];
      }
    );
  }

  if (!Object.keys(symbolTimeframes).length && Array.isArray(data.symbols)) {
    data.symbols.forEach((symbol: string) => {
      symbolTimeframes[symbol] = Array.isArray(data.timeframes) ? data.timeframes : [];
    });
  }

  return {
    symbols: (data.symbols || []) as Symbol[],
    timeframes: (data.timeframes || []) as Timeframe[],
    symbolTimeframes,
  };
}

export interface SymbolDetails {
  symbol_name: string;
  base_asset: string;
  quote_asset: string;
  image_path: string | null;
  price: number | null;
  volume_24h: number | null;
  market_cap: number | null;
  circulating_supply: number | null;
  timestamp: string | null;
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

// Symbol Filter API (Whitelist/Blacklist)
export interface SymbolFilter {
  symbol: string;
  filter_type: "whitelist" | "blacklist";
  created_at?: string;
  updated_at?: string;
}

export interface SymbolFilterCheck {
  symbol: string;
  is_whitelisted: boolean;
  is_blacklisted: boolean;
  filter_type: "whitelist" | "blacklist" | null;
}

export async function fetchSymbolFilters(
  filterType?: "whitelist" | "blacklist"
): Promise<SymbolFilter[]> {
  const url = filterType
    ? `${API_URL}/symbol-filters?filter_type=${filterType}`
    : `${API_URL}/symbol-filters`;
  const response = await fetch(url);
  if (!response.ok) throw new Error("Failed to fetch symbol filters");
  return response.json();
}

export async function addSymbolFilter(
  symbol: string,
  filterType: "whitelist" | "blacklist"
): Promise<SymbolFilter> {
  const response = await fetch(`${API_URL}/symbol-filters`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, filter_type: filterType }),
  });
  if (!response.ok) throw new Error("Failed to add symbol filter");
  return response.json();
}

export async function removeSymbolFilter(symbol: string): Promise<void> {
  const response = await fetch(`${API_URL}/symbol-filters/${symbol}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error("Failed to remove symbol filter");
}

export async function checkSymbolFilter(symbol: string): Promise<SymbolFilterCheck> {
  const response = await fetch(`${API_URL}/symbol-filters/${symbol}/check`);
  if (!response.ok) throw new Error("Failed to check symbol filter");
  return response.json();
}

