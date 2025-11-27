import { Suspense } from "react";
import { fetchSignals } from "@/lib/api/server";
import { SignalsClient } from "./signals-client";
import { Card } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/error/ErrorBoundary";

interface SignalsPageProps {
  searchParams: {
    symbol?: string;
    direction?: string;
    limit?: string;
  };
}

function SignalsSkeleton() {
  return (
    <Card className="p-12">
      <div className="text-center">
        <p className="text-muted-foreground">Loading signals...</p>
      </div>
    </Card>
  );
}

export default async function SignalsPage({ searchParams }: SignalsPageProps) {
  const limit = parseInt(searchParams.limit || "5000", 10);

  // Server-side fetch with caching
  const signals = await fetchSignals(
    {
      symbol: searchParams.symbol,
      direction: searchParams.direction,
      limit,
    },
    { next: { revalidate: 30 } } // Cache for 30 seconds
  );

  return (
    <ErrorBoundary>
      <Suspense fallback={<SignalsSkeleton />}>
        <SignalsClient initialSignals={signals} />
      </Suspense>
    </ErrorBoundary>
  );
}

