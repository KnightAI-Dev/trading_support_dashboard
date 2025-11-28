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
  {
    type: "ZigZag",
    name: "ZigZag",
    category: "Trend",
    description: "ZigZag indicator showing swing highs and lows",
    defaultSettings: { 
      depth: 12,
      deviation: 5,
      backstep: 2,
      lineWidth: 2,
      upColor: "#00e677",
      downColor: "#ff5252",
    },
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

