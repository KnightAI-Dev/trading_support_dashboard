"use client";

import { TradingSignal } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatTimestamp } from "@/lib/utils";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { memo } from "react";

interface ChartHeaderProps {
  symbol: string;
  timeframe: string;
  signal: TradingSignal | null;
  signalIndex: number;
  totalSignals: number;
  isLoadingSignals: boolean;
  onPreviousSignal: () => void;
  onNextSignal: () => void;
}

function ChartHeaderComponent({
  symbol,
  timeframe,
  signal,
  signalIndex,
  totalSignals,
  isLoadingSignals,
  onPreviousSignal,
  onNextSignal,
}: ChartHeaderProps) {
  return (
    <div className="mb-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          {symbol.replace("USDT", "/USDT")} - {timeframe}
        </h2>
        {signal && (
          <div className="flex items-center gap-2">
            <Badge
              variant={signal.direction === "long" ? "long" : "short"}
            >
              {signal.direction.toUpperCase()}
            </Badge>
            <span className="text-xs text-muted-foreground">
              {formatTimestamp(signal.timestamp)}
            </span>
            {/* Signal Navigation */}
            <div className="flex items-center gap-1 ml-2">
              <Button
                variant="outline"
                size="sm"
                onClick={onNextSignal}
                disabled={signalIndex <= 0 || isLoadingSignals}
                className="h-7 w-7 p-0"
                title="Next signal (newer)"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground px-2">
                {totalSignals > 0 
                  ? `${signalIndex + 1} / ${totalSignals}`
                  : "0 / 0"}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={onPreviousSignal}
                disabled={signalIndex >= totalSignals - 1 || isLoadingSignals}
                className="h-7 w-7 p-0"
                title="Previous signal (older)"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export const ChartHeader = memo(ChartHeaderComponent);

