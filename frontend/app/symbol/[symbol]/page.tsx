"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMarketStore } from "@/stores/useMarketStore";
import { fetchSignals, TradingSignal, fetchCandles, Candle, fetchSymbolDetails, SymbolDetails } from "@/lib/api";
import { ChartContainer } from "@/components/chart/ChartContainer";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ConfluenceBadges } from "@/components/ui/ConfluenceBadge";
import { formatPrice, formatTimestamp, formatNumber, formatSupply, formatPercent } from "@/lib/utils";
import { ArrowLeft, TrendingUp, TrendingDown, Target, XCircle, CheckCircle, ArrowUp, ArrowDown } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";
import { useWebSocket } from "@/hooks/useWebSocket";
import { subscribeToSymbolUpdates } from "@/hooks/useSymbolData";

export default function SymbolDetailPage() {
  const params = useParams();
  const router = useRouter();
  // Get symbol from URL and ensure it ends with USDT
  let symbolParam = (params.symbol as string).toUpperCase().replace("/", "");
  const symbol = symbolParam.endsWith("USDT") ? symbolParam : symbolParam + "USDT";
  const { setSelectedSymbol, setLatestSignal } = useMarketStore();

  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [symbolDetails, setSymbolDetails] = useState<SymbolDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [priceChange24h, setPriceChange24h] = useState<number | null>(null);
  const [stats, setStats] = useState({
    total: 0,
    wins: 0,
    losses: 0,
    winRate: 0,
    avgScore: 0,
    long: 0,
    short: 0,
  });

  // WebSocket connection for real-time updates
  useWebSocket(symbol, "1h");

  useEffect(() => {
    const loadData = async () => {
      setIsLoading(true);
      try {
        setSelectedSymbol(symbol);
        const [fetchedSignals, fetchedCandles, fetchedDetails] = await Promise.all([
          fetchSignals({ symbol, limit: 100 }),
          fetchCandles(symbol, "1h", 200),
          fetchSymbolDetails(symbol).catch(() => null), // Don't fail if details not available
        ]);

        setSignals(fetchedSignals);
        setCandles(fetchedCandles);
        setSymbolDetails(fetchedDetails);
        if (fetchedSignals.length > 0) {
          setLatestSignal(fetchedSignals[0]);
        }

        // Calculate 24h price change from candles
        if (fetchedCandles.length >= 24) {
          const currentPrice = fetchedCandles[0]?.close;
          const price24hAgo = fetchedCandles[23]?.close;
          if (currentPrice && price24hAgo && price24hAgo > 0) {
            const change = ((currentPrice - price24hAgo) / price24hAgo) * 100;
            setPriceChange24h(change);
          }
        }

        // Calculate statistics
        const total = fetchedSignals.length;
        const wins = fetchedSignals.filter((s) => {
          // Simplified: assume TP1 hit if signal exists (would need actual trade results)
          return s.tp1 && s.market_score && s.market_score >= 75;
        }).length;
        const losses = fetchedSignals.filter((s) => {
          return s.sl && s.market_score && s.market_score < 60;
        }).length;
        const long = fetchedSignals.filter((s) => s.direction === "long").length;
        const short = fetchedSignals.filter((s) => s.direction === "short").length;
        const avgScore =
          fetchedSignals.reduce((sum, s) => sum + (s.market_score || 0), 0) / total || 0;

        setStats({
          total,
          wins,
          losses,
          winRate: total > 0 ? (wins / total) * 100 : 0,
          avgScore,
          long,
          short,
        });
      } catch (error) {
        console.error("Error loading symbol data:", error);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [symbol, setSelectedSymbol, setLatestSignal]);

  // Subscribe to real-time symbol updates
  useEffect(() => {
    const unsubscribe = subscribeToSymbolUpdates((update) => {
      if (update.symbol === symbol) {
        setSymbolDetails((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            price: update.price ?? prev.price,
            volume_24h: update.volume_24h ?? prev.volume_24h,
            market_cap: update.marketcap ?? prev.market_cap,
          };
        });
      }
    });

    return unsubscribe;
  }, [symbol]);

  const displaySymbol = symbol.replace("USDT", "/USDT");
  const priceChangeColor = priceChange24h !== null && priceChange24h >= 0 ? "text-green-400" : "text-red-400";
  const priceChangeIcon = priceChange24h !== null && priceChange24h >= 0 ? ArrowUp : ArrowDown;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background p-4 md:p-6">
        <div className="max-w-[1920px] mx-auto">
          <div className="text-center py-12">
            <p className="text-muted-foreground">Loading symbol data...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      <div className="max-w-[1920px] mx-auto space-y-4">
        {/* Symbol Information Header */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/dashboard">
                <Button variant="ghost" size="sm">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  Back
                </Button>
              </Link>
              
              {/* Symbol Image */}
              {symbolDetails?.image_path ? (
                <img
                  src={symbolDetails.image_path}
                  alt={displaySymbol}
                  className="w-16 h-16 rounded-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              ) : (
                <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                  <span className="text-lg font-medium text-muted-foreground">
                    {symbolDetails?.base_asset?.charAt(0) || displaySymbol.charAt(0)}
                  </span>
                </div>
              )}
              
              <div>
                <h1 className="text-3xl font-bold text-foreground">{displaySymbol}</h1>
                <p className="text-sm text-muted-foreground mt-1">
                  {symbolDetails?.base_asset || ""} / {symbolDetails?.quote_asset || "USDT"}
                </p>
              </div>
            </div>

            {/* Price and Change */}
            <div className="text-right">
              <div className="text-3xl font-bold text-foreground">
                {formatPrice(symbolDetails?.price)}
              </div>
              {priceChange24h !== null && (
                <div className={`flex items-center gap-1 mt-1 ${priceChangeColor}`}>
                  {priceChange24h >= 0 ? (
                    <ArrowUp className="h-4 w-4" />
                  ) : (
                    <ArrowDown className="h-4 w-4" />
                  )}
                  <span className="text-lg font-semibold">
                    {formatPercent(priceChange24h)}
                  </span>
                  <span className="text-sm text-muted-foreground">(24h)</span>
                </div>
              )}
            </div>
          </div>
        </Card>

        {/* Market Data Stats */}
        {symbolDetails && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
            <Card className="p-4">
              <div className="text-sm text-muted-foreground mb-1">Market Cap</div>
              <div className="text-xl font-bold">
                {formatNumber(symbolDetails.market_cap)}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-sm text-muted-foreground mb-1">24h Volume</div>
              <div className="text-xl font-bold">
                {formatNumber(symbolDetails.volume_24h)}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-sm text-muted-foreground mb-1">Circulating Supply</div>
              <div className="text-xl font-bold">
                {formatSupply(symbolDetails.circulating_supply)}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-sm text-muted-foreground mb-1">Current Price</div>
              <div className="text-xl font-bold">
                {formatPrice(symbolDetails.price)}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-sm text-muted-foreground mb-1">24h Change</div>
              <div className={`text-xl font-bold ${priceChangeColor}`}>
                {priceChange24h !== null ? formatPercent(priceChange24h) : "-"}
              </div>
            </Card>
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">Total Signals</div>
            <div className="text-2xl font-bold">{stats.total}</div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">Win Rate</div>
            <div className="text-2xl font-bold text-green-400">
              {stats.winRate.toFixed(1)}%
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">Wins</div>
            <div className="text-2xl font-bold text-green-400 flex items-center gap-2">
              <CheckCircle className="h-5 w-5" />
              {stats.wins}
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">Losses</div>
            <div className="text-2xl font-bold text-red-400 flex items-center gap-2">
              <XCircle className="h-5 w-5" />
              {stats.losses}
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">Avg Score</div>
            <div className="text-2xl font-bold">{stats.avgScore.toFixed(1)}</div>
          </Card>
          <Card className="p-4">
            <div className="text-sm text-muted-foreground mb-1">Long / Short</div>
            <div className="text-sm font-medium">
              <span className="text-green-400">{stats.long}</span> /{" "}
              <span className="text-red-400">{stats.short}</span>
            </div>
          </Card>
        </div>

        {/* Chart */}
        <Card className="p-4">
          <div className="mb-4">
            <h2 className="text-lg font-semibold">Price Chart - 1h</h2>
          </div>
          <ChartContainer height={500} />
        </Card>

        {/* Signal History */}
        <Card className="p-4">
          <h2 className="text-lg font-semibold mb-4">Signal History</h2>
          <div className="space-y-2 max-h-[600px] overflow-y-auto">
            {signals.map((signal, index) => (
              <motion.div
                key={signal.id || index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
                className="p-4 border rounded-lg hover:bg-muted/50 transition-colors cursor-pointer"
                onClick={() => {
                  setLatestSignal(signal);
                  router.push("/dashboard");
                }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 space-y-2">
                    <div className="flex items-center gap-3">
                      <Badge
                        variant={signal.direction === "long" ? "long" : "short"}
                        className="flex items-center gap-1"
                      >
                        {signal.direction === "long" ? (
                          <TrendingUp className="h-3 w-3" />
                        ) : (
                          <TrendingDown className="h-3 w-3" />
                        )}
                        {signal.direction.toUpperCase()}
                      </Badge>
                      <span
                        className={`text-sm font-semibold ${
                          (signal.market_score || 0) >= 90
                            ? "text-emerald-400"
                            : (signal.market_score || 0) >= 75
                            ? "text-green-400"
                            : "text-yellow-400"
                        }`}
                      >
                        Score: {signal.market_score || 0}
                      </span>
                      {signal.confluence && (
                        <ConfluenceBadges confluence={signal.confluence} />
                      )}
                      <span className="text-xs text-muted-foreground">
                        {formatTimestamp(signal.timestamp)}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">Entry: </span>
                        <span className="font-medium">
                          {formatPrice(signal.entry1 || signal.price)}
                        </span>
                      </div>
                      {signal.sl && (
                        <div>
                          <span className="text-muted-foreground">SL: </span>
                          <span className="font-medium text-red-400">
                            {formatPrice(signal.sl)}
                          </span>
                        </div>
                      )}
                      {signal.tp1 && (
                        <div>
                          <span className="text-muted-foreground">TP1: </span>
                          <span className="font-medium text-green-400">
                            {formatPrice(signal.tp1)}
                          </span>
                        </div>
                      )}
                      {signal.tp2 && (
                        <div>
                          <span className="text-muted-foreground">TP2: </span>
                          <span className="font-medium text-green-400">
                            {formatPrice(signal.tp2)}
                          </span>
                        </div>
                      )}
                      {signal.tp3 && (
                        <div>
                          <span className="text-muted-foreground">TP3: </span>
                          <span className="font-medium text-green-400">
                            {formatPrice(signal.tp3)}
                          </span>
                        </div>
                      )}
                    </div>

                    {signal.swing_high && signal.swing_low && (
                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        <span>
                          Swing High: <span className="text-foreground">{formatPrice(signal.swing_high)}</span>
                        </span>
                        <span>
                          Swing Low: <span className="text-foreground">{formatPrice(signal.swing_low)}</span>
                        </span>
                      </div>
                    )}

                    {signal.risk_reward_ratio && (
                      <div className="text-xs text-muted-foreground">
                        Risk/Reward:{" "}
                        <span className="text-foreground font-medium">
                          {signal.risk_reward_ratio.toFixed(2)}x
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
            {signals.length === 0 && (
              <div className="text-center py-8 text-muted-foreground">
                No signals found for this symbol
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}

