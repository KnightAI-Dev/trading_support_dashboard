"use client";

import { useState } from "react";
import { Star, GripVertical } from "lucide-react";
import { SymbolItem } from "./SymbolManager";
import { SymbolRow } from "./SymbolRow";
import { cn } from "@/lib/utils";

interface FavoritesSectionProps {
  items: SymbolItem[];
  favorites: string[];
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onToggleFavorite: (symbol: string) => void;
  onReorder: (newOrder: string[]) => void;
}

export function FavoritesSection({
  items,
  favorites,
  selectedSymbol,
  onSelect,
  onToggleFavorite,
  onReorder,
}: FavoritesSectionProps) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  };

  const handleDragLeave = () => {
    setDragOverIndex(null);
  };

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === dropIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }

    const newFavorites = [...favorites];
    const [removed] = newFavorites.splice(draggedIndex, 1);
    newFavorites.splice(dropIndex, 0, removed);

    onReorder(newFavorites);
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  };

  return (
    <div className="border-b border-border">
      <div className="px-4 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
        Favorites
      </div>
      <div className="divide-y divide-border">
        {items.map((item, index) => {
          const isDragging = draggedIndex === index;
          const isDragOver = dragOverIndex === index;

          return (
            <div
              key={item.symbol}
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, index)}
              onDragEnd={handleDragEnd}
              className={cn(
                "group relative flex items-center",
                isDragging && "opacity-50",
                isDragOver && "border-t-2 border-primary"
              )}
            >
              {/* Drag Handle */}
              <div className="absolute left-0 top-0 bottom-0 w-6 flex items-center justify-center cursor-move opacity-0 group-hover:opacity-100 transition-opacity">
                <GripVertical className="h-4 w-4 text-muted-foreground" />
              </div>

              {/* Symbol Row */}
              <div className="flex-1 ml-6">
                <SymbolRow
                  item={item}
                  isSelected={item.symbol === selectedSymbol}
                  isFavorite={true}
                  onSelect={onSelect}
                  onToggleFavorite={onToggleFavorite}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

