export type Timeframe = "1m" | "5m" | "15m" | "1h" | "4h" | string;
export type Symbol = "BTCUSDT" | "ETHUSDT" | "SOLUSDT" | string;
export type Direction = "long" | "short";
export type ConfluenceType = "OB" | "SR" | "RSI" | "CVD" | "FIB" | "Trend";

export const DEFAULT_SYMBOLS: Symbol[] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"];
export const DEFAULT_TIMEFRAMES: Timeframe[] = ["1m", "5m", "15m", "1h", "4h"];

export interface ChartSettings {
  showFibs: boolean;
  showOrderBlocks: boolean;
  showSR: boolean;
  showSwings: boolean;
  showEntrySLTP: boolean;
  showRSI: boolean;
  rsiHeight: number; // Height percentage (0-100) for RSI pane
  showTooltip: boolean;
  showMA7: boolean;
  showMA25: boolean;
  showMA99: boolean;
}

export interface Settings {
  fibLevels: {
    long: {
      entry1: number;
      entry2: number;
      sl: number;
      approaching: number;
    };
    short: {
      entry1: number;
      entry2: number;
      sl: number;
      approaching: number;
    };
    pullbackStart: number;
  };
  slMultipliers: {
    tp1: number;
    tp2: number;
    tp3: number;
  };
  minScore: number;
  confluenceWeights: {
    ob: number;
    sr: number;
    rsi: number;
    cvd: number;
    fib: number;
    trend: number;
  };
  swingDetection: {
    lookbackPeriods: number;
    strength: number;
  };
}

export const DEFAULT_SETTINGS: Settings = {
  fibLevels: {
    long: {
      entry1: 0.7,
      entry2: 0.72,
      sl: 0.9,
      approaching: 0.618,
    },
    short: {
      entry1: 0.618,
      entry2: 0.69,
      sl: 0.789,
      approaching: 0.5,
    },
    pullbackStart: 0.382,
  },
  slMultipliers: {
    tp1: 1.5,
    tp2: 2.0,
    tp3: 3.0,
  },
  minScore: 60,
  confluenceWeights: {
    ob: 20,
    sr: 20,
    rsi: 15,
    cvd: 15,
    fib: 15,
    trend: 15,
  },
  swingDetection: {
    lookbackPeriods: 5,
    strength: 5,
  },
};

