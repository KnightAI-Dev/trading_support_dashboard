"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { List, type RowComponentProps } from "react-window";
import { Card, CardContent } from "@/components/ui/card";
import { useSignalsStore } from "@/stores/useSignalsStore";
import { SignalRow } from "./SignalRow";
import type { SymbolItem } from "@/components/ui/SymbolManager";
import { Inbox } from "lucide-react";

interface SignalListProps {
  signalIds: string[];
  symbols?: SymbolItem[];
  rowHeight?: number;
  overscanCount?: number;
}

type SignalListRowData = {
  ids: string[];
  priceMap: Record<string, number>;
};

type VirtualizedRowProps = RowComponentProps<SignalListRowData>;

const DEFAULT_ROW_HEIGHT = 90;
const MIN_LIST_HEIGHT = 640;
const HEIGHT_OFFSET = 320;

const rowsAreEqual = (prev: VirtualizedRowProps, next: VirtualizedRowProps) => {
  if (prev.index !== next.index) return false;

  const prevSignalId = prev.ids[prev.index];
  const nextSignalId = next.ids[next.index];
  if (prevSignalId !== nextSignalId) return false;

  // Get signals to access their symbols for price lookup
  const prevSignal = useSignalsStore.getState().signalMap[prevSignalId];
  const nextSignal = useSignalsStore.getState().signalMap[nextSignalId];
  
  if (!prevSignal || !nextSignal) return prevSignal === nextSignal;
  
  // Compare prices using symbol as key (priceMap is keyed by symbol, not signalId)
  const prevPrice = prev.priceMap[prevSignal.symbol];
  const nextPrice = next.priceMap[nextSignal.symbol];
  if (prevPrice !== nextPrice) return false;

  return true;
};

const VirtualizedRowBase = ({
  index,
  style,
  ids,
  priceMap,
  ariaAttributes,
}: VirtualizedRowProps) => {
  const signalId = ids[index];
  const signal = useSignalsStore((state) => state.signalMap[signalId]);
  const currentPrice = signal ? priceMap[signal.symbol] ?? null : null;

  if (!signal) {
    return <div {...ariaAttributes} style={style} className="px-1" />;
  }

  return (
    <div {...ariaAttributes} style={style} className="px-1">
      <SignalRow signal={signal} currentPrice={currentPrice} />
    </div>
  );
};

const MemoizedVirtualizedRow = memo(VirtualizedRowBase, rowsAreEqual);
MemoizedVirtualizedRow.displayName = "VirtualizedRow";
const VirtualizedRowRenderer = (props: VirtualizedRowProps) => (
  <MemoizedVirtualizedRow {...props} />
);

function SignalTableHeader() {
  return (
    <div
      className="grid grid-cols-[150px_100px_80px_100px_100px_100px_100px_100px_100px_100px_120px_120px_80px_120px_100px] gap-4 items-center w-full border-b-2 border-border bg-muted/30 px-4 py-3 text-xs font-semibold text-muted-foreground uppercase sticky top-0 z-10 backdrop-blur-sm"
      role="rowheader"
      aria-label="Signal table header"
    >
      <div>Symbol</div>
      <div>Direction</div>
      <div>Timeframe</div>
      <div className="text-center">Score</div>
      <div className="text-center">Current</div>
      <div className="text-center">Entry</div>
      <div className="text-center">SL</div>
      <div className="text-center">TP1</div>
      <div className="text-center">TP2</div>
      <div className="text-center">TP3</div>
      <div className="text-center">Swing High</div>
      <div className="text-center">Swing Low</div>
      <div className="text-center">Confluence</div>
      <div className="text-center">Updated</div>
      <div className="text-center">Action</div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <Card className="w-full max-w-md border-dashed">
        <CardContent className="flex flex-col items-center justify-center p-12 text-center">
          <Inbox className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-semibold text-foreground mb-2">No signals found</h3>
          <p className="text-sm text-muted-foreground">
            Try adjusting your filters to see more results.
          </p>
        </CardContent>
      </Card>
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
  const [containerWidth, setContainerWidth] = useState<number>(1200);
  const [listHeight, setListHeight] = useState<number>(MIN_LIST_HEIGHT);

  // Initialize dimensions and set up observers on mount (only once)
  useEffect(() => {
    if (typeof window === "undefined") return;
    
    const node = containerRef.current;
    if (!node) return;
    
    // Set initial dimensions
    setListHeight(Math.max(window.innerHeight - HEIGHT_OFFSET, MIN_LIST_HEIGHT));
    setContainerWidth(node.clientWidth);
    
    // Set up window resize listener
    const handleResize = () => {
      setListHeight(Math.max(window.innerHeight - HEIGHT_OFFSET, MIN_LIST_HEIGHT));
    };
    window.addEventListener("resize", handleResize);
    
    // Set up ResizeObserver for container width changes
    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      observer = new ResizeObserver((entries) => {
        if (!Array.isArray(entries) || !entries.length) return;
        const entry = entries[0];
        setContainerWidth(entry.contentRect.width);
      });
      observer.observe(node);
    }
    
    return () => {
      window.removeEventListener("resize", handleResize);
      observer?.disconnect();
    };
  }, []); // Empty deps - set up once, observe container regardless of signal count

  const priceMap = useMemo<Record<string, number>>(() => {
    const map: Record<string, number> = {};
    symbols.forEach((symbol) => {
      if (typeof symbol.price === "number") {
        map[symbol.symbol] = symbol.price;
      }
    });
    return map;
  }, [symbols]);

  const rowData = useMemo<SignalListRowData>(
    () => ({
      ids: signalIds,
      priceMap,
    }),
    [signalIds, priceMap]
  );

  const computedWidth = Math.max(containerWidth, 320);
  const headerHeight = 48;
  const availableHeight = listHeight - headerHeight;

  return (
    <div
      ref={containerRef}
      className="w-full flex-1 flex flex-col rounded-lg border bg-card overflow-hidden"
      style={{ height: listHeight, minHeight: MIN_LIST_HEIGHT }}
      role="table"
      aria-label="Trading signals table"
      aria-rowcount={signalIds.length}
    >
      <SignalTableHeader />
      {!signalIds.length ? (
        <EmptyState />
      ) : (
        <div
          className="flex-1 overflow-hidden"
          style={{ height: availableHeight }}
        >
          <List<SignalListRowData>
            defaultHeight={availableHeight}
            style={{ height: availableHeight, width: computedWidth }}
            rowCount={signalIds.length}
            rowHeight={rowHeight}
            rowComponent={VirtualizedRowRenderer}
            rowProps={rowData}
            overscanCount={overscanCount}
          />
        </div>
      )}
    </div>
  );
}
