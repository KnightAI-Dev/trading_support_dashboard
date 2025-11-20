"use client";

import { useMarketStore } from "@/stores/useMarketStore";
import { Timeframe } from "@/lib/types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function TimeframeSelector() {
  const {
    selectedTimeframe,
    selectedSymbol,
    setSelectedTimeframe,
    symbolTimeframes,
    availableTimeframes,
  } = useMarketStore();

  const timeframes =
    symbolTimeframes[selectedSymbol] && symbolTimeframes[selectedSymbol].length
      ? symbolTimeframes[selectedSymbol]
      : availableTimeframes;

  return (
    <Select
      value={selectedTimeframe}
      onValueChange={(value) => setSelectedTimeframe(value as Timeframe)}
      disabled={!timeframes.length}
    >
      <SelectTrigger className="w-[100px]">
        <SelectValue placeholder="Timeframe" />
      </SelectTrigger>
      <SelectContent>
        {timeframes.map((tf) => (
          <SelectItem key={tf} value={tf}>
            {tf}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

