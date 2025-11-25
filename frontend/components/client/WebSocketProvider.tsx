"use client";

import { createContext, useContext, ReactNode, useEffect } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useMarketStore } from "@/stores/useMarketStore";

interface WebSocketContextValue {
  connect: () => void;
  disconnect: () => void;
  candles: any[];
  signals: any[];
  swingPoints: any[];
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { selectedSymbol, selectedTimeframe } = useMarketStore();
  const { connect, disconnect } = useWebSocket(selectedSymbol, selectedTimeframe);
  
  // Get real-time data from store
  const candles = useMarketStore((state) => state.candles);
  const signals = useMarketStore((state) => state.signals);
  const swingPoints = useMarketStore((state) => state.swingPoints);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return (
    <WebSocketContext.Provider value={{ connect, disconnect, candles, signals, swingPoints }}>
      {children}
    </WebSocketContext.Provider>
  );
}

export function useWebSocketContext() {
  const ctx = useContext(WebSocketContext);
  if (!ctx) {
    throw new Error("useWebSocketContext must be used within WebSocketProvider");
  }
  return ctx;
}

