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
  confluenceValue?: number | string; // Confluence value from 0 to 3 (number or string)
}

// Get color based on confluence value (0-3)
// Value 1 = Red, Value 2 = Yellow, Value 3 = Green
function getConfluenceColor(value: number | string): string {
  // Parse string to number if needed
  const numValue = typeof value === "string" ? parseInt(value, 10) : value;
  // Clamp value to 0-3 range
  const clampedValue = Math.max(0, Math.min(3, Math.floor(numValue)));
  
  switch (clampedValue) {
    case 0:
      return "bg-gray-500/20 text-gray-400 border-gray-500/50";
    case 1:
      return "bg-red-500/20 text-red-400 border-red-500/50";
    case 2:
      return "bg-yellow-500/20 text-yellow-400 border-yellow-500/50";
    case 3:
      return "bg-green-500/20 text-green-400 border-green-500/50";
    default:
      return "bg-gray-500/20 text-gray-400 border-gray-500/50";
  }
}

export function ConfluenceBadges({ confluence, className, confluenceValue }: ConfluenceBadgesProps) {
  if (!confluence) return null;
  // Get color from confluence value (1, 2, or 3)
  const colorClass = confluenceValue !== undefined 
    ? getConfluenceColor(confluenceValue)
    : "bg-gray-500/20 text-gray-400 border-gray-500/50";

  return (
    <div className={cn("flex flex-wrap gap-1 justify-center", className)}>
        <Badge
          variant="outline"
          className={cn(
            "text-xs font-medium px-2 py-0.5",
            colorClass
          )}
        >
          {confluenceValue}
        </Badge>
    </div>
  );
}

