"use client";

import { ConfluenceType } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ConfluenceBadgeProps {
  type: ConfluenceType;
  className?: string;
}

const confluenceColors: Record<ConfluenceType, string> = {
  OB: "bg-blue-500/20 text-blue-400 border-blue-500/50",
  SR: "bg-purple-500/20 text-purple-400 border-purple-500/50",
  RSI: "bg-yellow-500/20 text-yellow-400 border-yellow-500/50",
  CVD: "bg-cyan-500/20 text-cyan-400 border-cyan-500/50",
  FIB: "bg-green-500/20 text-green-400 border-green-500/50",
  Trend: "bg-orange-500/20 text-orange-400 border-orange-500/50",
};

export function ConfluenceBadge({ type, className }: ConfluenceBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "text-xs font-medium px-2 py-0.5",
        confluenceColors[type],
        className
      )}
    >
      {type}
    </Badge>
  );
}

interface ConfluenceBadgesProps {
  confluence: string[] | string | null | undefined;
  className?: string;
}

export function ConfluenceBadges({ confluence, className }: ConfluenceBadgesProps) {
  // Handle null, undefined, or empty values
  if (!confluence) return null;

  // Normalize to array
  let types: ConfluenceType[];
  
  if (typeof confluence === "string") {
    // Handle comma-separated string
    types = confluence.split(",").map((s) => s.trim() as ConfluenceType).filter(Boolean);
  } else if (Array.isArray(confluence)) {
    // Already an array
    types = confluence.filter(Boolean) as ConfluenceType[];
  } else {
    // Invalid type, return null
    return null;
  }

  if (types.length === 0) return null;

  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {types.map((type, index) => (
        <ConfluenceBadge key={`${type}-${index}`} type={type as ConfluenceType} />
      ))}
    </div>
  );
}

