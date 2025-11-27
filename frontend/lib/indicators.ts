import { IndicatorDefinition } from "@/lib/types";

export const INDICATOR_REGISTRY: IndicatorDefinition[] = [
  {
    type: "RSI",
    name: "Relative Strength Index",
    category: "Oscillators",
    description: "Measures the speed and magnitude of price changes",
    defaultSettings: { period: 14 },
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
    description: "Exponentially weighted moving average",
    defaultSettings: { period: 20 },
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

