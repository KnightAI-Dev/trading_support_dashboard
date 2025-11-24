"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Star } from "lucide-react";
import { SymbolItem } from "./SymbolManager";
import { cn } from "@/lib/utils";

interface SymbolRowProps {
  item: SymbolItem;
  isSelected: boolean;
  isFavorite: boolean;
  onSelect: (symbol: string) => void;
  onToggleFavorite: (symbol: string) => void;
}

const formatNumber = (num: number | undefined): string => {
  if (!num || num === 0) return "N/A";
  if (num >= 1e12) return `${(num / 1e12).toFixed(2)}T`;
  if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
  if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
  if (num >= 1e3) return `${(num / 1e3).toFixed(2)}K`;
  return num.toFixed(2);
};

export function SymbolRow({
  item,
  isSelected,
  isFavorite,
  onSelect,
  onToggleFavorite,
}: SymbolRowProps) {
  const router = useRouter();
  const changeColor =
    item.change24h >= 0 ? "text-green-500" : "text-red-500";
  const changeSign = item.change24h >= 0 ? "+" : "";
  const [imageError, setImageError] = useState(false);

  const handleStarClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggleFavorite(item.symbol);
  };

  const handleRowClick = () => {
    // Select symbol for dashboard
    onSelect(item.symbol);
  };

  const handleImageOrNameClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    // Navigate to symbol detail page
    router.push(`/symbol/${item.symbol}`);
  };

  return (
    <div
      onClick={handleRowClick}
      className={cn(
        "flex items-center justify-between px-4 py-2 cursor-pointer transition-colors",
        "hover:bg-muted/50",
        isSelected && "bg-primary/10 border-l-2 border-primary"
      )}
    >
      {/* Left: Symbol with Image */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        {/* Symbol Image */}
        {item.image_url && !imageError ? (
          <img
            src={item.image_url}
            alt={item.symbol}
            onClick={handleImageOrNameClick}
            className="w-8 h-8 rounded-full flex-shrink-0 object-cover cursor-pointer hover:opacity-80 transition-opacity"
            onError={() => {
              setImageError(true);
            }}
          />
        ) : (
          <div
            onClick={handleImageOrNameClick}
            className="w-8 h-8 rounded-full flex-shrink-0 bg-muted flex items-center justify-center cursor-pointer hover:opacity-80 transition-opacity"
          >
            <span className="text-xs font-medium text-muted-foreground">
              {item.base.charAt(0)}
            </span>
          </div>
        )}
        {/* Symbol Info */}
        <div className="flex flex-col min-w-0 flex-1">
          <div
            onClick={handleImageOrNameClick}
            className="text-sm font-medium text-foreground truncate cursor-pointer hover:underline"
          >
            {item.base}/{item.quote}
          </div>
          <div className="text-xs text-muted-foreground truncate">
            {item.symbol}
          </div>
        </div>
      </div>

      {/* Mid: Price, Market Cap, and Volume */}
      <div className="flex flex-col items-end mx-3 min-w-[120px]">
        <div className="text-sm font-medium text-foreground">
          ${item.price.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 8,
          })}
        </div>
        <div className={cn("text-xs", changeColor)}>
          {changeSign}
          {item.change24h.toFixed(2)}%
        </div>
        {item.marketcap !== undefined && (
          <div className="text-xs text-muted-foreground mt-1">
            MCap: ${formatNumber(item.marketcap)}
          </div>
        )}
        {item.volume_24h !== undefined && (
          <div className="text-xs text-muted-foreground">
            Vol: ${formatNumber(item.volume_24h)}
          </div>
        )}
      </div>

      {/* Right: Star Icon */}
      <button
        onClick={handleStarClick}
        className={cn(
          "ml-2 p-1 rounded hover:bg-muted transition-colors",
          "focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-1"
        )}
        aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
      >
        <Star
          className={cn(
            "h-4 w-4 transition-colors",
            isFavorite
              ? "fill-yellow-400 text-yellow-400"
              : "text-muted-foreground hover:text-yellow-400"
          )}
        />
      </button>
    </div>
  );
}

