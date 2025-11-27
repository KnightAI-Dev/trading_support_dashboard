"use client";

import { TradingSignal } from "@/lib/api";
import { MarketScore } from "@/components/ui/MarketScore";
import { ConfluenceBadges } from "@/components/ui/ConfluenceBadge";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatPrice } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";
import { memo } from "react";

interface SignalInfoPanelProps {
  signal: TradingSignal | null;
  currentPrice: number | null;
  entryPrice: number | null;
  marketScore: number;
  signalIndex: number;
  totalSignals: number;
}

function SignalInfoPanelComponent({
  signal,
  currentPrice,
  entryPrice,
  marketScore,
  signalIndex,
  totalSignals,
}: SignalInfoPanelProps) {
  return (
    <div className="space-y-4">
      {/* Market Score */}
      <Card className="p-6">
        <MarketScore 
          score={marketScore} 
          currentPrice={currentPrice}
          entryPrice={entryPrice}
        />
      </Card>

      {/* Signal Info */}
      {signal ? (
        <Card className="p-4">
          <h3 className="text-sm font-semibold mb-4">
            Signal {totalSignals > 0 ? `${signalIndex + 1} / ${totalSignals}` : ""}
          </h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Direction</span>
              <Badge
                variant={signal.direction === "long" ? "long" : "short"}
              >
                {signal.direction === "long" ? (
                  <TrendingUp className="h-3 w-3 mr-1" />
                ) : (
                  <TrendingDown className="h-3 w-3 mr-1" />
                )}
                {signal.direction.toUpperCase()}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Entry</span>
              <span className="text-sm font-medium">
                {formatPrice(signal.entry1 || signal.price)}
              </span>
            </div>

            {signal.sl && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Stop Loss</span>
                <span className="text-sm font-medium text-red-400">
                  {formatPrice(signal.sl)}
                </span>
              </div>
            )}

            {signal.tp1 && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">TP1</span>
                <span className="text-sm font-medium text-green-400">
                  {formatPrice(signal.tp1)}
                </span>
              </div>
            )}

            {signal.tp2 && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">TP2</span>
                <span className="text-sm font-medium text-green-400">
                  {formatPrice(signal.tp2)}
                </span>
              </div>
            )}

            {signal.tp3 && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">TP3</span>
                <span className="text-sm font-medium text-green-400">
                  {formatPrice(signal.tp3)}
                </span>
              </div>
            )}

            {signal.swing_high && signal.swing_low && (
              <>
                <div className="flex items-center justify-between pt-2 border-t">
                  <span className="text-xs text-muted-foreground">Swing High</span>
                  <span className="text-sm font-medium">
                    {formatPrice(signal.swing_high)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Swing Low</span>
                  <span className="text-sm font-medium">
                    {formatPrice(signal.swing_low)}
                  </span>
                </div>
              </>
            )}

            {signal.confluence && (
              <div className="pt-2 border-t">
                <span className="text-xs text-muted-foreground block mb-2">
                  Confluence
                </span>
                <ConfluenceBadges confluence={signal.confluence} />
              </div>
            )}

            {signal.risk_reward_ratio && (
              <div className="flex items-center justify-between pt-2 border-t">
                <span className="text-xs text-muted-foreground">Risk/Reward</span>
                <span className="text-sm font-medium">
                  {signal.risk_reward_ratio.toFixed(2)}x
                </span>
              </div>
            )}
          </div>
        </Card>
      ) : (
        <Card className="p-4">
          <p className="text-sm text-muted-foreground text-center">
            No signal available
          </p>
        </Card>
      )}
    </div>
  );
}

export const SignalInfoPanel = memo(SignalInfoPanelComponent);

