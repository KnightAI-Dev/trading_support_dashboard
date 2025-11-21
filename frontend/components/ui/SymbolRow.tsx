"use client";

import { useState } from "react";
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

export function SymbolRow({
  item,
  isSelected,
  isFavorite,
  onSelect,
  onToggleFavorite,
}: SymbolRowProps) {
  const changeColor =
    item.change24h >= 0 ? "text-green-500" : "text-red-500";
  const changeSign = item.change24h >= 0 ? "+" : "";
  const [imageError, setImageError] = useState(false);

  const handleStarClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onToggleFavorite(item.symbol);
  };

  return (
    <div
      onClick={() => onSelect(item.symbol)}
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
            className="w-8 h-8 rounded-full flex-shrink-0 object-cover"
            onError={() => {
              setImageError(true);
            }}
          />
        ) : (
          <div className="w-8 h-8 rounded-full flex-shrink-0 bg-muted flex items-center justify-center">
            <span className="text-xs font-medium text-muted-foreground">
              {item.base.charAt(0)}
            </span>
          </div>
        )}
        {/* Symbol Info */}
        <div className="flex flex-col min-w-0 flex-1">
          <div className="text-sm font-medium text-foreground truncate">
            {item.base}/{item.quote}
          </div>
          <div className="text-xs text-muted-foreground truncate">
            {item.symbol}
          </div>
        </div>
      </div>

      {/* Mid: Price */}
      <div className="flex flex-col items-end mx-3 min-w-[80px]">
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

