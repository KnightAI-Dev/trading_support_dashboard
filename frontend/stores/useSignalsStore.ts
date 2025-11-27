"use client";

import { create } from "zustand";
import { TradingSignal } from "@/lib/api";

type SignalMap = Record<string, TradingSignal>;

const MAX_SIGNALS = 10000;
  
interface SignalStoreState {
  signalMap: SignalMap;
  signalIds: string[];
  revision: number;
  setInitialSignals(signals: TradingSignal[]): void;
  updateBatch(batch: TradingSignal[]): void;
  clear(): void;
}

const getSignalTimestamp = (signal?: TradingSignal) =>
  signal ? new Date(signal.timestamp).getTime() : 0;

const sortIdsByTimestamp = (map: SignalMap) =>
  Object.keys(map).sort((a, b) => getSignalTimestamp(map[b]) - getSignalTimestamp(map[a]));

const shouldUpdateSignal = (current: TradingSignal | undefined, next: TradingSignal) => {
  if (!current) return true;
  if (current.timestamp !== next.timestamp) return true;
  if (current.price !== next.price) return true;
  if ((current.entry1 ?? current.price) !== (next.entry1 ?? next.price)) return true;
  if ((current.market_score ?? 0) !== (next.market_score ?? 0)) return true;
  if (current.direction !== next.direction) return true;
  if (current.sl !== next.sl) return true;
  if (current.tp1 !== next.tp1) return true;
  if (current.tp2 !== next.tp2) return true;
  if (current.tp3 !== next.tp3) return true;
  return false;
};

export const useSignalsStore = create<SignalStoreState>()((set, get) => ({
  signalMap: {},
  signalIds: [],
  revision: 0,
  setInitialSignals(signals) {
    const nextMap: SignalMap = {};
    signals.forEach((signal) => {
      if (signal?.id === undefined || signal === null) return;
      nextMap[String(signal.id)] = signal;
    });

    let sortedIds = sortIdsByTimestamp(nextMap);
    if (sortedIds.length > MAX_SIGNALS) {
      sortedIds = sortedIds.slice(0, MAX_SIGNALS);
    }

    const limitedMap: SignalMap = {};
    sortedIds.forEach((id) => {
      limitedMap[id] = nextMap[id];
    });

    set({
      signalMap: limitedMap,
      signalIds: sortedIds,
      revision: Date.now(),
    });
  },
  updateBatch(batch) {
    if (!batch.length) return;

    const currentMap = get().signalMap;
    const nextMap: SignalMap = { ...currentMap };
    let hasChanges = false;

    batch.forEach((signal) => {
      if (!signal || signal.id === undefined || signal.id === null) return;
      const id = String(signal.id);
      const existing = nextMap[id];

      if (shouldUpdateSignal(existing, signal)) {
        nextMap[id] = existing ? { ...existing, ...signal } : signal;
        hasChanges = true;
      }
    });

    if (!hasChanges) return;

    let sortedIds = sortIdsByTimestamp(nextMap);
    if (sortedIds.length > MAX_SIGNALS) {
      sortedIds = sortedIds.slice(0, MAX_SIGNALS);
    }

    const limitedMap: SignalMap = {};
    sortedIds.forEach((id) => {
      limitedMap[id] = nextMap[id];
    });

    set((state) => ({
      signalMap: limitedMap,
      signalIds: sortedIds,
      revision: state.revision + 1,
    }));
  },
  clear() {
    set({ signalMap: {}, signalIds: [], revision: 0 });
  },
}));

export type { SignalStoreState };


