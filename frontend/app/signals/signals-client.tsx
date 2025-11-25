"use client";

import { useState, useMemo, useEffect } from "react";
import { useRouter } from "next/navigation";
import { TradingSignal } from "@/lib/api";
import { useWebSocketContext } from "@/components/client/WebSocketProvider";
import { SignalsTable } from "@/components/table/SignalsTable";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Search, Filter, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface SignalsClientProps {
  initialSignals: TradingSignal[];
}

export function SignalsClient({ initialSignals }: SignalsClientProps) {
  const router = useRouter();
  const { signals: wsSignals } = useWebSocketContext();
  const [searchTerm, setSearchTerm] = useState("");
  const [directionFilter, setDirectionFilter] = useState<string>("all");
  const [minScore, setMinScore] = useState<number>(0);

  // Merge initial signals with WebSocket updates
  const allSignals = useMemo(() => {
    if (!wsSignals.length) return initialSignals;
    
    // Merge: WebSocket signals override initial signals
    const signalMap = new Map(initialSignals.map(s => [s.id, s]));
    wsSignals.forEach(s => signalMap.set(s.id, s));
    
    return Array.from(signalMap.values()).sort(
      (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  }, [initialSignals, wsSignals]);

  // Client-side filtering
  const filteredSignals = useMemo(() => {
    let filtered = [...allSignals];

    if (searchTerm) {
      filtered = filtered.filter((signal) =>
        signal.symbol.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (directionFilter !== "all") {
      filtered = filtered.filter((signal) => signal.direction === directionFilter);
    }

    if (minScore > 0) {
      filtered = filtered.filter((signal) => (signal.market_score || 0) >= minScore);
    }

    return filtered;
  }, [allSignals, searchTerm, directionFilter, minScore]);

  const handleRowClick = (signal: TradingSignal) => {
    router.push(`/dashboard`);
  };

  return (
    <div className="min-h-screen bg-background p-4 md:p-6">
      <div className="max-w-[1920px] mx-auto space-y-4">
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
              <h1 className="text-2xl font-bold text-foreground">Signals Table</h1>
              <p className="text-sm text-muted-foreground mt-1">
                {filteredSignals.length} signal{filteredSignals.length !== 1 ? "s" : ""} found
              </p>
            </div>
          </div>
        </div>

        {/* Filters */}
        <Card className="p-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-[200px]">
              <Label htmlFor="search" className="sr-only">
                Search
              </Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search by symbol..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Label htmlFor="direction">Direction:</Label>
              <Select value={directionFilter} onValueChange={setDirectionFilter}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="long">Long</SelectItem>
                  <SelectItem value="short">Short</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-2">
              <Label htmlFor="min-score">Min Score:</Label>
              <Input
                id="min-score"
                type="number"
                min="0"
                max="100"
                value={minScore}
                onChange={(e) => setMinScore(Number(e.target.value))}
                className="w-[100px]"
              />
            </div>
          </div>
        </Card>

        {/* Table */}
        <SignalsTable signals={filteredSignals} onRowClick={handleRowClick} />
      </div>
    </div>
  );
}

