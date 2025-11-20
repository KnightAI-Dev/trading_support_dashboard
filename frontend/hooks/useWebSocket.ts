import { useEffect, useRef, useCallback } from "react";
import { useMarketStore } from "@/stores/useMarketStore";
import { TradingSignal, Candle, SwingPoint } from "@/lib/api";
import { notifySymbolUpdate } from "@/hooks/useSymbolData";
import { SymbolItem } from "@/components/ui/SymbolManager";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

export type WebSocketEvent =
  | { type: "signal"; data: TradingSignal }
  | { type: "candle"; data: Candle }
  | { type: "swing"; data: SwingPoint }
  | { type: "symbol_update"; data: Partial<SymbolItem> }
  | { type: "marketcap_update"; data: Partial<SymbolItem> }
  | { type: "indicator"; data: any }
  | { type: "connected" | "subscribed" | "error"; message?: string; symbol?: string; timeframe?: string };

export function useWebSocket(symbol?: string, timeframe?: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 10;
  const reconnectDelay = useRef(1000); // Start with 1 second

  const {
    addSignal,
    addCandle,
    addSwingPoint,
    selectedSymbol,
    selectedTimeframe,
    setError,
  } = useMarketStore();

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("WebSocket connected to:", WS_URL);
        reconnectAttempts.current = 0;
        reconnectDelay.current = 1000;
        setError(null);

        // Subscribe to symbol and timeframe
        const currentSymbol = symbol || selectedSymbol;
        const currentTimeframe = timeframe || selectedTimeframe;
        const subscribeMessage = {
          type: "subscribe",
          symbol: currentSymbol,
          timeframe: currentTimeframe,
        };
        console.log("Subscribing to:", subscribeMessage);
        ws.send(JSON.stringify(subscribeMessage));
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "symbol_update") {
            if (message.data.symbol === "BTCUSDT") {
              console.log("current time:", new Date().toISOString());
              console.log("timestamp:", message.data.timestamp);
              console.log("BTCUSDT price updated:", message.data.price);
            }
          }
          // console.log("WebSocket message received:", message);
          handleMessage(message);
        } catch (error) {
          console.error("Error parsing WebSocket message:", error);
        }
      };

      ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        setError("WebSocket connection error");
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        wsRef.current = null;

        // Attempt reconnection
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectDelay.current);
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000); // Max 30 seconds
        } else {
          setError("WebSocket connection lost. Please refresh the page.");
        }
      };
    } catch (error) {
      console.error("Error connecting WebSocket:", error);
      setError("Failed to connect to WebSocket");
    }
  }, [symbol, timeframe, selectedSymbol, selectedTimeframe, setError]);

  const handleMessage = useCallback(
    (message: WebSocketEvent) => {
      switch (message.type) {
        case "signal":
          addSignal(message.data);
          break;
        case "candle":
          addCandle(message.data);
          break;
        case "swing":
          addSwingPoint(message.data);
          break;
        case "symbol_update":
          // Notify symbol data subscribers about the update
          notifySymbolUpdate(message.data);
          break;
        case "marketcap_update":
          // Notify symbol data subscribers about market cap/volume update
          notifySymbolUpdate(message.data);
          break;
        case "connected":
        case "subscribed":
          // Handle connection/subscription confirmations
          console.log("WebSocket:", message.type, message.message);
          break;
        case "indicator":
          // Handle indicator updates
          console.log("Indicator update:", message.data);
          break;
        default:
          console.warn("Unknown WebSocket message type:", message);
      }
    },
    [addSignal, addCandle, addSwingPoint]
  );

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  useEffect(() => {
    // Disconnect previous connection
    disconnect();

    // Always try to connect if we have a WebSocket URL
    if (WS_URL) {
      connect();
    } else {
      // Fallback to polling if WebSocket is not available
      console.log("WebSocket not configured, using REST API polling");
    }

    return () => {
      disconnect();
    };
  }, [symbol, timeframe, selectedSymbol, selectedTimeframe, connect, disconnect]);

  return { connect, disconnect };
}

