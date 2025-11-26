"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { ArrowLeft, Save } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import {
  fetchStrategyConfig,
  updateStrategyConfigs,
  StrategyConfig,
  fetchIngestionConfig,
  updateIngestionConfigs,
  IngestionConfig,
  fetchSymbolFilters,
  addSymbolFilter,
  removeSymbolFilter,
  SymbolFilter,
} from "@/lib/api";
import { ErrorBoundary } from "@/components/error/ErrorBoundary";

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

        {/* Configuration Tabs */}
        <Tabs defaultValue="strategy" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="strategy">Strategy Config</TabsTrigger>
            <TabsTrigger value="ingestion">Ingestion Config</TabsTrigger>
            <TabsTrigger value="filters">Symbol Filters</TabsTrigger>
          </TabsList>
          <TabsContent value="strategy">
        <StrategyConfigTab />
          </TabsContent>
          <TabsContent value="ingestion">
            <IngestionConfigTab />
          </TabsContent>
          <TabsContent value="filters">
            <SymbolFiltersTab />
          </TabsContent>
        </Tabs>
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

  // Helper function to safely convert config values to string for numeric inputs
  const getNumericValue = (value: string | number | object | undefined): string => {
    if (value === undefined || value === null) return "";
    if (typeof value === "string") return value;
    if (typeof value === "number") return String(value);
    // If it's an object, return empty string (shouldn't happen for numeric fields)
    return "";
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
                  value={getNumericValue(config.market_data_limit)}
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
                  value={getNumericValue(config.symbol_limit)}
                  onChange={(e) => handleUpdate("symbol_limit", e.target.value)}
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
                  value={getNumericValue(config.bullish_fib_level_lower)}
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
                  value={getNumericValue(config.bullish_fib_level_higher)}
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
                  value={getNumericValue(config.bullish_sl_fib_level)}
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
                  value={getNumericValue(config.bearish_fib_level)}
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
                  value={getNumericValue(config.bearish_sl_fib_level)}
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
                  value={getNumericValue(config.tp1_fib_level)}
                  onChange={(e) => handleUpdate("tp1_fib_level", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tp2_fib_level">TP2 Fib Level</Label>
                <Input
                  id="tp2_fib_level"
                  type="number"
                  step="0.001"
                  value={getNumericValue(config.tp2_fib_level)}
                  onChange={(e) => handleUpdate("tp2_fib_level", e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tp3_fib_level">TP3 Fib Level</Label>
                <Input
                  id="tp3_fib_level"
                  type="number"
                  step="0.001"
                  value={getNumericValue(config.tp3_fib_level)}
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
                  value={getNumericValue(config.candle_counts_for_swing_high_low)}
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
                  value={getNumericValue(config.sensible_window)}
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
                  value={getNumericValue(config.swing_window)}
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

// Ingestion Configuration Component
function IngestionConfigTab() {
  const [config, setConfig] = useState<IngestionConfig>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setIsLoading(true);
    try {
      const data = await fetchIngestionConfig();
      setConfig(data);
    } catch (error) {
      console.error("Error loading ingestion config:", error);
      setSaveMessage("Error loading configuration");
      setTimeout(() => setSaveMessage(null), 3000);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdate = (key: string, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  // Helper function to safely convert config values to string for numeric inputs
  const getNumericValue = (value: string | number | undefined): string => {
    if (value === undefined || value === null) return "";
    if (typeof value === "string") return value;
    if (typeof value === "number") return String(value);
    return "";
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveMessage(null);
    try {
      // Convert all values to strings for API
      const configsToSave: Record<string, string> = {};
      for (const [key, value] of Object.entries(config)) {
        configsToSave[key] = String(value);
      }
      await updateIngestionConfigs(configsToSave);
      
      // Trigger ingestion service to reload symbols
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        await fetch(`${API_URL}/ingestion-config/reload`, {
          method: "POST",
        });
      } catch (reloadError) {
        console.warn("Failed to trigger ingestion reload:", reloadError);
        // Don't fail the save operation if reload fails
      }
      
      setSaveMessage("Ingestion configuration saved successfully! Symbols will be updated.");
      setTimeout(() => setSaveMessage(null), 3000);
      
      // Wait a few seconds for ingestion service to update symbols, then refresh frontend
      setTimeout(() => {
        // Dispatch custom event to trigger refresh in other components
        window.dispatchEvent(new CustomEvent('ingestionConfigUpdated'));
        
        // Also refresh if we're on the dashboard
        if (typeof window !== 'undefined') {
          // Trigger a page refresh or reload market metadata
          const refreshEvent = new CustomEvent('refreshMarketData');
          window.dispatchEvent(refreshEvent);
        }
      }, 3000); // Wait 3 seconds for ingestion service to process
    } catch (error) {
      console.error("Error saving ingestion config:", error);
      setSaveMessage("Error saving configuration");
      setTimeout(() => setSaveMessage(null), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <p className="text-muted-foreground">Loading ingestion configuration...</p>
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
          <div>
            <h3 className="text-lg font-semibold">Ingestion Configuration</h3>
            <p className="text-sm text-muted-foreground mt-1">
              Configure data ingestion parameters for Binance and CoinGecko
            </p>
          </div>
          <Button onClick={handleSave} disabled={isSaving}>
            <Save className="h-4 w-4 mr-2" />
            {isSaving ? "Saving..." : "Save"}
          </Button>
        </div>

        <div className="space-y-6">
          {/* Binance Filters */}
          <div className="space-y-4">
            <h4 className="text-sm font-medium">Binance Filters</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="limit_volume_up">
                  Minimum 24h Volume (USD)
                </Label>
                <Input
                  id="limit_volume_up"
                  type="number"
                  value={getNumericValue(config.limit_volume_up)}
                  onChange={(e) =>
                    handleUpdate("limit_volume_up", e.target.value)
                  }
                  placeholder="50000000"
                />
                <p className="text-xs text-muted-foreground">
                  Minimum 24h volume filter for Binance perpetuals in USD
                </p>
              </div>
            </div>
          </div>

          {/* CoinGecko Filters */}
          <div className="space-y-4 pt-4 border-t">
            <h4 className="text-sm font-medium">CoinGecko Filters</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="limit_market_cap">
                  Minimum Market Cap (USD)
                </Label>
                <Input
                  id="limit_market_cap"
                  type="number"
                  value={getNumericValue(config.limit_market_cap)}
                  onChange={(e) =>
                    handleUpdate("limit_market_cap", e.target.value)
                  }
                  placeholder="50000000"
                />
                <p className="text-xs text-muted-foreground">
                  Minimum market cap filter from CoinGecko in USD
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="coingecko_limit">
                  CoinGecko Limit
                </Label>
                <Input
                  id="coingecko_limit"
                  type="number"
                  value={getNumericValue(config.coingecko_limit)}
                  onChange={(e) =>
                    handleUpdate("coingecko_limit", e.target.value)
                  }
                  placeholder="250"
                />
                <p className="text-xs text-muted-foreground">
                  Number of top coins to fetch from CoinGecko by market cap
                </p>
              </div>
            </div>
          </div>

          {/* Backfill Configuration */}
          <div className="space-y-4 pt-4 border-t">
            <h4 className="text-sm font-medium">Backfill Configuration</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="backfill_limit">
                  Backfill Limit
                </Label>
                <Input
                  id="backfill_limit"
                  type="number"
                  value={getNumericValue(config.backfill_limit)}
                  onChange={(e) =>
                    handleUpdate("backfill_limit", e.target.value)
                  }
                  placeholder="400"
                  min="1"
                  max="10000"
                />
                <p className="text-xs text-muted-foreground">
                  Number of recent candles to fetch per symbol/timeframe during backfill operations
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}

// Symbol Filters Component
function SymbolFiltersTab() {
  const [whitelist, setWhitelist] = useState<SymbolFilter[]>([]);
  const [blacklist, setBlacklist] = useState<SymbolFilter[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newSymbol, setNewSymbol] = useState("");
  const [selectedFilterType, setSelectedFilterType] = useState<"whitelist" | "blacklist">("whitelist");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    loadFilters();
  }, []);

  const loadFilters = async () => {
    setIsLoading(true);
    try {
      const [whitelistData, blacklistData] = await Promise.all([
        fetchSymbolFilters("whitelist"),
        fetchSymbolFilters("blacklist"),
      ]);
      setWhitelist(whitelistData);
      setBlacklist(blacklistData);
    } catch (error) {
      console.error("Error loading symbol filters:", error);
      setMessage("Error loading filters");
      setTimeout(() => setMessage(null), 3000);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!newSymbol.trim()) {
      setMessage("Please enter a symbol");
      setTimeout(() => setMessage(null), 3000);
      return;
    }

    const symbol = newSymbol.trim().toUpperCase();
    try {
      await addSymbolFilter(symbol, selectedFilterType);
      setNewSymbol("");
      setMessage(`${symbol} added to ${selectedFilterType}`);
      setTimeout(() => setMessage(null), 3000);
      await loadFilters();
      
      // Trigger ingestion reload
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        await fetch(`${API_URL}/ingestion-config/reload`, {
          method: "POST",
        });
      } catch (reloadError) {
        console.warn("Failed to trigger ingestion reload:", reloadError);
      }
    } catch (error) {
      console.error("Error adding symbol filter:", error);
      setMessage("Error adding symbol filter");
      setTimeout(() => setMessage(null), 3000);
    }
  };

  const handleRemove = async (symbol: string) => {
    try {
      await removeSymbolFilter(symbol);
      setMessage(`${symbol} removed from filters`);
      setTimeout(() => setMessage(null), 3000);
      await loadFilters();
      
      // Trigger ingestion reload
      try {
        const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        await fetch(`${API_URL}/ingestion-config/reload`, {
          method: "POST",
        });
      } catch (reloadError) {
        console.warn("Failed to trigger ingestion reload:", reloadError);
      }
    } catch (error) {
      console.error("Error removing symbol filter:", error);
      setMessage("Error removing symbol filter");
      setTimeout(() => setMessage(null), 3000);
    }
  };

  if (isLoading) {
    return (
      <Card className="p-6">
        <p className="text-muted-foreground">Loading symbol filters...</p>
      </Card>
    );
  }

  return (
    <>
      {message && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="p-4 bg-primary/10 border border-primary/20 rounded-lg text-sm text-primary"
        >
          {message}
        </motion.div>
      )}

      <Card className="p-6">
        <div className="mb-6">
          <h3 className="text-lg font-semibold mb-2">Symbol Filters</h3>
          <p className="text-sm text-muted-foreground">
            Manage whitelist and blacklist for symbol ingestion. Blacklist overrides whitelist.
            Whitelisted symbols are always ingested (skip market cap/volume filters).
            Blacklisted symbols are never ingested.
          </p>
        </div>

        {/* Add Symbol Form */}
        <div className="mb-6 p-4 border rounded-lg space-y-4">
          <h4 className="text-sm font-medium">Add Symbol Filter</h4>
          <div className="flex gap-2">
            <Input
              placeholder="Enter symbol (e.g., BTCUSDT)"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
              onKeyPress={(e) => {
                if (e.key === "Enter") {
                  handleAdd();
                }
              }}
              className="flex-1"
            />
            <select
              value={selectedFilterType}
              onChange={(e) => setSelectedFilterType(e.target.value as "whitelist" | "blacklist")}
              className="px-3 py-2 border rounded-md bg-background"
            >
              <option value="whitelist">Whitelist</option>
              <option value="blacklist">Blacklist</option>
            </select>
            <Button onClick={handleAdd}>Add</Button>
          </div>
        </div>

        {/* Whitelist */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium">Whitelist ({whitelist.length})</h4>
            <span className="text-xs text-muted-foreground">
              Always ingested, bypasses market cap/volume filters
            </span>
          </div>
          {whitelist.length === 0 ? (
            <p className="text-sm text-muted-foreground p-4 border rounded-lg">
              No whitelisted symbols
            </p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {whitelist.map((filter) => (
                <div
                  key={filter.symbol}
                  className="flex items-center justify-between p-2 border rounded-lg bg-green-50 dark:bg-green-950/20"
                >
                  <span className="text-sm font-mono">{filter.symbol}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemove(filter.symbol)}
                    className="h-6 w-6 p-0"
                  >
                    ×
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Blacklist */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium">Blacklist ({blacklist.length})</h4>
            <span className="text-xs text-muted-foreground">
              Never ingested, overrides whitelist
            </span>
          </div>
          {blacklist.length === 0 ? (
            <p className="text-sm text-muted-foreground p-4 border rounded-lg">
              No blacklisted symbols
            </p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {blacklist.map((filter) => (
                <div
                  key={filter.symbol}
                  className="flex items-center justify-between p-2 border rounded-lg bg-red-50 dark:bg-red-950/20"
                >
                  <span className="text-sm font-mono">{filter.symbol}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRemove(filter.symbol)}
                    className="h-6 w-6 p-0"
                  >
                    ×
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Card>
    </>
  );
}

