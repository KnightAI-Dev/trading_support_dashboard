"use client";

import { useState } from "react";
import { shallow } from "zustand/shallow";
import { useMarketStore } from "@/stores/useMarketStore";
import { TimeframeSelector } from "@/components/ui/TimeframeSelector";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { RefreshCw, BarChart3 } from "lucide-react";
import { IndicatorSelector } from "@/components/chart/IndicatorSelector";

interface ChartControlsProps {
  onRefreshSwings: () => void;
  isRefreshingSwings: boolean;
}

export function ChartControls({ onRefreshSwings, isRefreshingSwings }: ChartControlsProps) {
  const [indicatorDialogOpen, setIndicatorDialogOpen] = useState(false);

  const chartSettings = useMarketStore((state) => state.chartSettings);

  const { updateChartSettings, addIndicator, removeIndicator } = useMarketStore(
    (state) => ({
      updateChartSettings: state.updateChartSettings,
      addIndicator: state.addIndicator,
      removeIndicator: state.removeIndicator,
    }),
    shallow
  );

  return (
    <div className="flex flex-wrap items-center gap-4 p-4 bg-card rounded-lg border">
      <div className="flex items-center gap-2">
        <Label htmlFor="timeframe">Timeframe:</Label>
        <TimeframeSelector />
      </div>
      <div className="flex-1" />

      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-2">
          <Switch
            id="show-swings"
            checked={chartSettings.showSwings}
            onCheckedChange={(checked: boolean) =>
              updateChartSettings({ showSwings: checked })
            }
          />
          <Label htmlFor="show-swings" className="text-sm cursor-pointer">
            Swings
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="show-entry"
            checked={chartSettings.showEntrySLTP}
            onCheckedChange={(checked: boolean) =>
              updateChartSettings({ showEntrySLTP: checked })
            }
          />
          <Label htmlFor="show-entry" className="text-sm cursor-pointer">
            Entry/SL/TP
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <Switch
            id="show-tooltip"
            checked={chartSettings.showTooltip}
            onCheckedChange={(checked: boolean) =>
              updateChartSettings({ showTooltip: checked })
            }
          />
          <Label htmlFor="show-tooltip" className="text-sm cursor-pointer">
            Tooltip
          </Label>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setIndicatorDialogOpen(true)}
          className="flex items-center gap-2"
        >
          <BarChart3 className="h-4 w-4" />
          Indicators
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onRefreshSwings}
          disabled={isRefreshingSwings}
          className="flex items-center gap-2"
        >
          <RefreshCw className={`h-4 w-4 ${isRefreshingSwings ? "animate-spin" : ""}`} />
          Refresh Swings
        </Button>
      </div>

      <IndicatorSelector
        open={indicatorDialogOpen}
        onOpenChange={setIndicatorDialogOpen}
        activeIndicators={chartSettings.activeIndicators || []}
        onAddIndicator={addIndicator}
        onRemoveIndicator={removeIndicator}
      />
    </div>
  );
}

