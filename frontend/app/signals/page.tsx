import { Suspense } from "react";
import { fetchSignals } from "@/lib/api/server";
import { SignalsClient } from "./signals-client";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/error/ErrorBoundary";
import { Loader2 } from "lucide-react";

interface SignalsPageProps {
  searchParams: {
    symbol?: string;
    direction?: string;
    limit?: string;
  };
}

function SignalsSkeleton() {
  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto flex max-w-[1920px] flex-col gap-6 p-4 md:p-6 lg:p-8">
        {/* Header Skeleton */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="h-9 w-20 bg-muted animate-pulse rounded-md" />
            <div>
              <div className="h-9 w-48 bg-muted animate-pulse rounded-md mb-2" />
              <div className="h-5 w-64 bg-muted animate-pulse rounded-md" />
            </div>
          </div>
          <div className="h-12 w-64 bg-muted animate-pulse rounded-lg" />
        </div>

        {/* Filters Skeleton */}
        <Card className="p-4 md:p-6">
          <div className="flex flex-wrap items-center gap-4 md:gap-6">
            <div className="h-10 w-full max-w-[300px] bg-muted animate-pulse rounded-md" />
            <div className="h-10 w-[140px] bg-muted animate-pulse rounded-md" />
            <div className="h-10 w-[200px] bg-muted animate-pulse rounded-md" />
          </div>
        </Card>

        {/* Table Skeleton */}
        <Card className="p-0 overflow-hidden">
          <div className="h-12 bg-muted/30 border-b" />
          <CardContent className="p-12">
            <div className="flex flex-col items-center justify-center">
              <Loader2 className="h-8 w-8 text-primary animate-spin mb-4" />
              <p className="text-sm text-muted-foreground">Loading signals...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default async function SignalsPage({ searchParams }: SignalsPageProps) {
  const limit = parseInt(searchParams.limit || "5000", 10);

  // Server-side fetch - disable caching for large requests to avoid 2MB cache limit
  const signals = await fetchSignals(
    {
      symbol: searchParams.symbol,
      direction: searchParams.direction,
      limit,
    },
    limit > 1000 ? { cache: 'no-store' } : { next: { revalidate: 30 } }
  );

  return (
    <ErrorBoundary>
      <Suspense fallback={<SignalsSkeleton />}>
        <SignalsClient initialSignals={signals} />
      </Suspense>
    </ErrorBoundary>
  );
}
