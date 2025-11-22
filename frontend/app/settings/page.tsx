"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft, Save } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  fetchStrategyConfig,
  updateStrategyConfigs,
  StrategyConfig,
} from "@/lib/api";

export default function SettingsPage() {

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      <div className="max-w-4xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link href="/dashboard">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back
              </Button>
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-foreground">Settings</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Configure trading parameters and indicators
              </p>
            </div>
          </div>
        </div>

        {/* Strategy Configuration */}
        <StrategyConfigTab />
      </div>
    </div>
  );
}

// Strategy Configuration Component
function StrategyConfigTab() {
  const [config, setConfig] = useState<StrategyConfig>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const data = await fetchStrategyConfig();
      setConfig(data);
    } catch (error) {
      console.error("Error loading strategy config:", error);
      setSaveMessage("Error loading configuration");
      setTimeout(() => setSaveMessage(null), 3000);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdate = (key: string, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage(null);
    try {
      // Convert all values to strings for API
      const configsToSave: Record<string, string> = {};
      for (const [key, value] of Object.entries(config)) {
        if (key === "swing_high_low_pruning_score") {
          // Keep JSON as string
          configsToSave[key] =
            typeof value === "string" ? value : JSON.stringify(value);
        } else {
          configsToSave[key] = String(value);
        }
      }
      await updateStrategyConfigs(configsToSave);
      setSaveMessage("Strategy configuration saved successfully!");
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (error) {
      console.error("Error saving strategy config:", error);
      setSaveMessage("Error saving configuration");
      setTimeout(() => setSaveMessage(null), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <p className="text-muted-foreground">Loading configuration...</p>
      </Card>
    );
  }

  return (
    <>
      {saveMessage && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 bg-primary/10 border border-primary/20 rounded-lg text-sm text-primary"
        >
          {saveMessage}
        </motion.div>
      )}

      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Strategy Configuration</h3>
          <Button onClick={handleSave} disabled={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>

        <div className="space-y-6">
          {/* Market Data Limits */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium">Market Data Limits</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="market_data_limit">Market Data Limit</Label>
                <Input
                  id="market_data_limit"
                  type="number"
                  value={config.market_data_limit || ""}
                  onChange={(e) =>
                    handleUpdate("market_data_limit", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="symbol_limit">Symbol Limit</Label>
                <Input
                  id="symbol_limit"
                  type="number"
                  value={config.symbol_limit || ""}
                  onChange={(e) => handleUpdate("symbol_limit", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="limit_market_cap">Min Market Cap (USD)</Label>
                <Input
                  id="limit_market_cap"
                  type="number"
                  value={config.limit_market_cap || ""}
                  onChange={(e) =>
                    handleUpdate("limit_market_cap", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="limit_volume_up">Min 24h Volume (USD)</Label>
                <Input
                  id="limit_volume_up"
                  type="number"
                  value={config.limit_volume_up || ""}
                  onChange={(e) =>
                    handleUpdate("limit_volume_up", e.target.value)
                  }
                />
              </div>
            </div>
          </div>

          {/* Fibonacci Levels */}
          <div className="space-y-4 pt-4 border-t">
            <h4 className="text-sm font-medium">Fibonacci Levels</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="bullish_fib_level_lower">
                  Bullish Fib Lower
                </Label>
                <Input
                  id="bullish_fib_level_lower"
                  type="number"
                  step="0.001"
                  value={config.bullish_fib_level_lower || ""}
                  onChange={(e) =>
                    handleUpdate("bullish_fib_level_lower", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bullish_fib_level_higher">
                  Bullish Fib Higher
                </Label>
                <Input
                  id="bullish_fib_level_higher"
                  type="number"
                  step="0.001"
                  value={config.bullish_fib_level_higher || ""}
                  onChange={(e) =>
                    handleUpdate("bullish_fib_level_higher", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bullish_sl_fib_level">
                  Bullish SL Fib Level
                </Label>
                <Input
                  id="bullish_sl_fib_level"
                  type="number"
                  step="0.001"
                  value={config.bullish_sl_fib_level || ""}
                  onChange={(e) =>
                    handleUpdate("bullish_sl_fib_level", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bearish_fib_level">Bearish Fib Level</Label>
                <Input
                  id="bearish_fib_level"
                  type="number"
                  step="0.001"
                  value={config.bearish_fib_level || ""}
                  onChange={(e) =>
                    handleUpdate("bearish_fib_level", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="bearish_sl_fib_level">
                  Bearish SL Fib Level
                </Label>
                <Input
                  id="bearish_sl_fib_level"
                  type="number"
                  step="0.001"
                  value={config.bearish_sl_fib_level || ""}
                  onChange={(e) =>
                    handleUpdate("bearish_sl_fib_level", e.target.value)
                  }
                />
              </div>
            </div>
          </div>

          {/* Take Profit Levels */}
          <div className="space-y-4 pt-4 border-t">
            <h4 className="text-sm font-medium">Take Profit Levels</h4>
            <div className="grid grid-cols-3 gap-4">
              <div className="space-y-2">
                <Label htmlFor="tp1_fib_level">TP1 Fib Level</Label>
                <Input
                  id="tp1_fib_level"
                  type="number"
                  step="0.001"
                  value={config.tp1_fib_level || ""}
                  onChange={(e) => handleUpdate("tp1_fib_level", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tp2_fib_level">TP2 Fib Level</Label>
                <Input
                  id="tp2_fib_level"
                  type="number"
                  step="0.001"
                  value={config.tp2_fib_level || ""}
                  onChange={(e) => handleUpdate("tp2_fib_level", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tp3_fib_level">TP3 Fib Level</Label>
                <Input
                  id="tp3_fib_level"
                  type="number"
                  step="0.001"
                  value={config.tp3_fib_level || ""}
                  onChange={(e) => handleUpdate("tp3_fib_level", e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Swing Detection */}
          <div className="space-y-4 pt-4 border-t">
            <h4 className="text-sm font-medium">Swing Detection</h4>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="candle_counts_for_swing_high_low">
                  Candle Counts for Swing High/Low
                </Label>
                <Input
                  id="candle_counts_for_swing_high_low"
                  type="number"
                  value={config.candle_counts_for_swing_high_low || ""}
                  onChange={(e) =>
                    handleUpdate(
                      "candle_counts_for_swing_high_low",
                      e.target.value
                    )
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sensible_window">Sensible Window</Label>
                <Input
                  id="sensible_window"
                  type="number"
                  value={config.sensible_window || ""}
                  onChange={(e) =>
                    handleUpdate("sensible_window", e.target.value)
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="swing_window">Swing Window</Label>
                <Input
                  id="swing_window"
                  type="number"
                  value={config.swing_window || ""}
                  onChange={(e) => handleUpdate("swing_window", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="swing_high_low_pruning_score">
                  Pruning Scores (JSON)
                </Label>
                <Input
                  id="swing_high_low_pruning_score"
                  type="text"
                  value={
                    typeof config.swing_high_low_pruning_score === "string"
                      ? config.swing_high_low_pruning_score
                      : JSON.stringify(
                          config.swing_high_low_pruning_score || {},
                          null,
                          2
                        )
                  }
                  onChange={(e) =>
                    handleUpdate(
                      "swing_high_low_pruning_score",
                      e.target.value
                    )
                  }
                />
                <p className="text-xs text-muted-foreground">
                  JSON format: {"{"}"BTCUSDT": 0.015, "ETHUSDT": 0.015{"}"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}

