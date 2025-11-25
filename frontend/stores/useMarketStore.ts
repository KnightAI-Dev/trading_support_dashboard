import { create } from "zustand";
import { Candle, SwingPoint, SRLevel, TradingSignal, MarketMetadata } from "@/lib/api";
import {
  Timeframe,
  Symbol,
  ChartSettings,
  DEFAULT_SYMBOLS,
  DEFAULT_TIMEFRAMES,
} from "@/lib/types";

interface MarketState {
  selectedSymbol: Symbol;
  selectedTimeframe: Timeframe;
  availableSymbols: Symbol[];
  availableTimeframes: Timeframe[];
  symbolTimeframes: Record<string, Timeframe[]>;
  candles: Candle[];
  swingPoints: SwingPoint[];
  srLevels: SRLevel[];
  signals: TradingSignal[];
  latestSignal: TradingSignal | null;
  chartSettings: ChartSettings;
  isLoading: boolean;
  error: string | null;

  // Actions
  setSelectedSymbol: (symbol: Symbol) => void;
  setSelectedTimeframe: (timeframe: Timeframe) => void;
  setCandles: (candles: Candle[]) => void;
  addCandle: (candle: Candle) => void;
  updateCandle: (candle: Candle) => void;
  setSwingPoints: (swings: SwingPoint[]) => void;
  addSwingPoint: (swing: SwingPoint) => void;
  setSRLevels: (levels: SRLevel[]) => void;
  setSignals: (signals: TradingSignal[]) => void;
  addSignal: (signal: TradingSignal) => void;
  setLatestSignal: (signal: TradingSignal | null) => void;
  updateChartSettings: (settings: Partial<ChartSettings>) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setMarketMetadata: (metadata: MarketMetadata) => void;
  reset: () => void;
}

const defaultChartSettings: ChartSettings = {
  showFibs: false,  // Hide Fibs by default
  showOrderBlocks: false,  // Hide Order Blocks by default
  showSR: false,  // Hide Support/Resistance by default
  showSwings: true,  // Always show Swing High/Low
  showEntrySLTP: true,  // Always show Entry/SL/TP
  showRSI: false,  // Hide RSI by default
  rsiHeight: 20,  // RSI takes 20% of chart height by default
  showTooltip: true,  // Show tooltip by default
  showMA7: false,  // Hide MA(7) by default
  showMA25: false,  // Hide MA(25) by default
  showMA99: false,  // Hide MA(99) by default
};

export const useMarketStore = create<MarketState>((set) => ({
  selectedSymbol: "BTCUSDT",
  selectedTimeframe: "1h",
  availableSymbols: DEFAULT_SYMBOLS,
  availableTimeframes: DEFAULT_TIMEFRAMES,
  symbolTimeframes: DEFAULT_SYMBOLS.reduce<Record<string, Timeframe[]>>((acc, symbol) => {
    acc[symbol] = [...DEFAULT_TIMEFRAMES];
    return acc;
  }, {}),
  candles: [],
  swingPoints: [],
  srLevels: [],
  signals: [],
  latestSignal: null,
  chartSettings: defaultChartSettings,
  isLoading: false,
  error: null,

  setSelectedSymbol: (symbol) => set({ selectedSymbol: symbol }),
  setSelectedTimeframe: (timeframe) => set({ selectedTimeframe: timeframe }),
  setCandles: (candles) => set({ candles }),
  addCandle: (candle) =>
    set((state) => {
      const existing = state.candles.findIndex(
        (c) => c.timestamp === candle.timestamp && c.symbol === candle.symbol
      );
      if (existing >= 0) {
        const updated = [...state.candles];
        updated[existing] = candle;
        return { candles: updated };
      }
      return { candles: [...state.candles, candle].sort((a, b) => 
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      ) };
    }),
  updateCandle: (candle) =>
    set((state) => {
      const index = state.candles.findIndex(
        (c) => c.timestamp === candle.timestamp && c.symbol === candle.symbol
      );
      if (index >= 0) {
        const updated = [...state.candles];
        updated[index] = candle;
        return { candles: updated };
      }
      return state;
    }),
  setSwingPoints: (swings) => {
    // Sort swing points by timestamp in ascending order before storing
    const sorted = Array.isArray(swings) 
      ? [...swings].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
      : [];
    set({ swingPoints: sorted });
  },
  addSwingPoint: (swing) =>
    set((state) => {
      // Check if this swing point already exists (same symbol, timeframe, type, timestamp, and price)
      const isDuplicate = state.swingPoints.some((s) => {
        const sameSymbol = s.symbol === swing.symbol;
        const sameTimeframe = s.timeframe === swing.timeframe;
        const sameType = s.type === swing.type;
        // Check if timestamp is within 1 second (to handle slight variations)
        const timestampDiff = Math.abs(
          new Date(s.timestamp).getTime() - new Date(swing.timestamp).getTime()
        );
        const sameTimestamp = timestampDiff < 1000;
        // Check if price is very close (within 0.01% to handle floating point differences)
        const priceDiff = Math.abs(s.price - swing.price);
        const priceTolerance = Math.max(s.price, swing.price) * 0.0001; // 0.01% tolerance
        const samePrice = priceDiff < priceTolerance;
        
        return sameSymbol && sameTimeframe && sameType && sameTimestamp && samePrice;
      });
      
      // If duplicate, don't add it
      if (isDuplicate) {
        return state;
      }
      
      // Add new swing and sort by timestamp
      const updated = [...state.swingPoints, swing].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );
      return { swingPoints: updated };
    }),
  setSRLevels: (levels) => set({ srLevels: Array.isArray(levels) ? levels : [] }),
  setSignals: (signals) => set({ signals }),
  addSignal: (signal) =>
    set((state) => ({
      signals: [signal, ...state.signals].slice(0, 1000), // Keep last 1000
      latestSignal: signal.symbol === state.selectedSymbol ? signal : state.latestSignal,
    })),
  setLatestSignal: (signal) => set({ latestSignal: signal }),
  updateChartSettings: (settings) =>
    set((state) => ({
      chartSettings: { ...state.chartSettings, ...settings },
    })),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setMarketMetadata: (metadata) =>
    set((state) => {
      const nextSymbolTimeframes =
        metadata.symbolTimeframes &&
        Object.keys(metadata.symbolTimeframes).length > 0
          ? Object.entries(metadata.symbolTimeframes).reduce<Record<string, Timeframe[]>>(
              (acc, [symbol, timeframes]) => {
                acc[symbol] = [...timeframes];
                return acc;
              },
              {}
            )
          : state.symbolTimeframes;

      return {
        availableSymbols:
          metadata.symbols && metadata.symbols.length
            ? metadata.symbols
            : state.availableSymbols,
        availableTimeframes:
          metadata.timeframes && metadata.timeframes.length
            ? metadata.timeframes
            : state.availableTimeframes,
        symbolTimeframes: nextSymbolTimeframes,
      };
    }),
  reset: () =>
    set({
      candles: [],
      swingPoints: [],
      srLevels: [],
      signals: [],
      latestSignal: null,
      isLoading: false,
      error: null,
    }),
}));

