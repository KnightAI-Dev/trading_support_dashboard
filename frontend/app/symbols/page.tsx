import { Suspense } from "react";
import { fetchSymbolsWithPrices } from "@/lib/api/server";
import { SymbolsClient } from "./symbols-client";
import { Card } from "@/components/ui/card";

function SymbolsSkeleton() {
  return (
    <Card className="p-12">
      <div className="text-center">
        <p className="text-muted-foreground">Loading symbols...</p>
      </div>
    </Card>
  );
}

export default async function SymbolsPage() {
  // Server-side fetch with caching
  const symbols = await fetchSymbolsWithPrices({ next: { revalidate: 30 } });

  return (
    <Suspense fallback={<SymbolsSkeleton />}>
      <SymbolsClient initialSymbols={symbols} />
    </Suspense>
  );
}

