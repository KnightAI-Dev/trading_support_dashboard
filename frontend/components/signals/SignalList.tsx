"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { List, type RowComponentProps } from "react-window";
import { Card } from "@/components/ui/card";
import { useSignalsStore } from "@/stores/useSignalsStore";
import { SignalRow } from "./SignalRow";
import type { SymbolItem } from "@/components/ui/SymbolManager";

interface SignalListProps {
  signalIds: string[];
  symbols?: SymbolItem[];
  rowHeight?: number;
  overscanCount?: number;
}

interface VirtualizedRowProps extends RowComponentProps<SignalListRowProps> {}

interface SignalListRowProps {
  ids: string[];
  symbols: SymbolItem[];
}

const DEFAULT_ROW_HEIGHT = 80;
const MIN_LIST_HEIGHT = 360;
const HEIGHT_OFFSET = 320;

const rowsAreEqual = (prev: VirtualizedRowProps, next: VirtualizedRowProps) =>
  prev.index === next.index &&
  prev.style === next.style &&
  prev.ids === next.ids &&
  prev.symbols === next.symbols &&
  prev["ariaAttributes"] === next["ariaAttributes"];

const VirtualizedRow = memo(
  ({ index, style, ids, symbols, ariaAttributes }: VirtualizedRowProps) => {
    const signalId = ids[index];
    const signal = useSignalsStore((state) => state.signalMap[signalId]);

    if (!signal) {
      return null;
    }

    return (
      <div {...ariaAttributes} style={style} className="px-1">
        <SignalRow signal={signal} symbols={symbols} />
      </div>
    );
  },
  rowsAreEqual
);

VirtualizedRow.displayName = "VirtualizedRow";

function SignalTableHeader() {
  return (
    <div className="grid grid-cols-[150px_100px_80px_100px_120px_100px_100px_100px_100px_100px_120px_120px_120px_100px] gap-4 items-center w-full border-b-2 border-border bg-muted/30 px-4 py-2 text-xs font-semibold text-muted-foreground uppercase sticky top-0 z-10">
      <div>Symbol</div>
      <div>Direction</div>
      <div>Timeframe</div>
      <div className="text-center">Score</div>
      <div className="text-right">Current</div>
      <div className="text-right">Entry</div>
      <div className="text-right">SL</div>
      <div className="text-right">TP1</div>
      <div className="text-right">TP2</div>
      <div className="text-right">TP3</div>
      <div className="text-right">Swing High</div>
      <div className="text-right">Swing Low</div>
      <div className="text-right">Updated</div>
      <div className="text-right">Action</div>
    </div>
  );
}

export function SignalList({
  signalIds,
  symbols = [],
  rowHeight = DEFAULT_ROW_HEIGHT,
  overscanCount = 20,
}: SignalListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mounted, setMounted] = useState(false);
  const [containerWidth, setContainerWidth] = useState<number>(() =>
    typeof window === "undefined" ? 1200 : window.innerWidth
  );
  const [listHeight, setListHeight] = useState<number>(() =>
    typeof window === "undefined"
      ? MIN_LIST_HEIGHT
      : Math.max(window.innerHeight - HEIGHT_OFFSET, MIN_LIST_HEIGHT)
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const handleResize = () => {
      setListHeight(Math.max(window.innerHeight - HEIGHT_OFFSET, MIN_LIST_HEIGHT));
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [mounted]);

  useEffect(() => {
    if (!mounted) return;
    const node = containerRef.current;
    if (!node || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver((entries) => {
      if (!Array.isArray(entries) || !entries.length) return;
      const entry = entries[0];
      setContainerWidth(entry.contentRect.width);
    });
    observer.observe(node);
    // Recalculate width immediately when ref is attached or data appears
    setContainerWidth(node.clientWidth);
    return () => observer.disconnect();
  }, [mounted, signalIds.length]);

  const rowProps = useMemo<SignalListRowProps>(
    () => ({
      ids: signalIds,
      symbols,
    }),
    [signalIds, symbols]
  );

  if (!mounted) {
    return <div className="h-[400px] w-full rounded-lg border border-dashed border-border/40" />;
  }

  const computedWidth = Math.max(containerWidth, 320);
  const headerHeight = 48;
  const availableHeight = listHeight - headerHeight;

  // Always render container structure - don't return early
  return (
    <div
      ref={containerRef}
      className="w-full flex-1 flex flex-col"
      style={{ height: listHeight, minHeight: MIN_LIST_HEIGHT }}
    >
      <SignalTableHeader />
      {!signalIds.length ? (
        <Card className="flex flex-1 items-center justify-center text-muted-foreground">
          No signals match the current filters.
        </Card>
      ) : (
        <div className="flex-1 overflow-hidden" style={{ height: availableHeight }}>
          <List
            defaultHeight={availableHeight}
            style={{ height: availableHeight, width: computedWidth }}
            rowCount={signalIds.length}
            rowHeight={rowHeight}
            rowProps={rowProps}
            rowComponent={VirtualizedRow}
            overscanCount={overscanCount}
          />
        </div>
      )}
    </div>
  );
}


