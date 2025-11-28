import { IndicatorDefinition } from "@/lib/types";

export const INDICATOR_REGISTRY: IndicatorDefinition[] = [
  {
    type: "RSI",
    name: "RSI",
    category: "Oscillators",
    description: "Measures the speed and magnitude of price changes",
    defaultSettings: { period: 14, paneHeight: 10 },
    requiresSeparatePane: true,
  },
  {
    type: "MACD",
    name: "Moving Average Convergence Divergence",
    category: "Oscillators",
    description: "Shows relationship between two moving averages",
    defaultSettings: { fastPeriod: 12, slowPeriod: 26, signalPeriod: 9 },
    requiresSeparatePane: true,
  },
  {
    type: "MA",
    name: "Moving Average",
    category: "Trend",
    description: "Simple moving average",
    defaultSettings: { period: 20 },
    requiresSeparatePane: false,
  },
  {
    type: "EMA",
    name: "Exponential Moving Average",
    category: "Trend",
    description: "Exponentially weighted moving average (20, 50, 100, 200)",
    defaultSettings: { 
      periods: [20, 50, 100, 200],
      colors: ["#3b82f6", "#f59e0b", "#8b5cf6", "#ef4444"], // Blue, Amber, Purple, Red
      lineWidth: 1,
    },
    requiresSeparatePane: false,
  },
  {
    type: "BB",
    name: "Bollinger Bands",
    category: "Volatility",
    description: "Price volatility bands",
    defaultSettings: { period: 20, stdDev: 2 },
    requiresSeparatePane: false,
  },
  {
    type: "Stochastic",
    name: "Stochastic Oscillator",
    category: "Oscillators",
    description: "Compares closing price to price range",
    defaultSettings: { kPeriod: 14, dPeriod: 3 },
    requiresSeparatePane: true,
  },
  {
    type: "Volume",
    name: "Volume",
    category: "Volume",
    description: "Trading volume indicator",
    defaultSettings: {},
    requiresSeparatePane: false,
  },
  {
    type: "SR",
    name: "Support/Resistance",
    category: "Trend",
    description: "Support and resistance levels",
    defaultSettings: {},
    requiresSeparatePane: false,
  },
];

export const getIndicatorsByCategory = () => {
  const categories: Record<string, IndicatorDefinition[]> = {};
  INDICATOR_REGISTRY.forEach((indicator) => {
    if (!categories[indicator.category]) {
      categories[indicator.category] = [];
    }
    categories[indicator.category].push(indicator);
  });
  return categories;
};

