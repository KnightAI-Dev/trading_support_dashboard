"use client";

import { useState, useMemo } from "react";
import { SimpleModal } from "@/components/ui/SimpleModal";
import { IndicatorConfig, IndicatorType } from "@/lib/types";
import { INDICATOR_REGISTRY, getIndicatorsByCategory } from "@/lib/indicators";
import { cn } from "@/lib/utils";

interface IndicatorSelectorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  activeIndicators: IndicatorConfig[];
  onAddIndicator: (type: IndicatorType) => void;
  onRemoveIndicator: (id: string) => void;
}

export function IndicatorSelector({
  open,
  onOpenChange,
  activeIndicators,
  onAddIndicator,
  onRemoveIndicator,
}: IndicatorSelectorProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("All");

  // Get categories for tabs
  const categories = useMemo(() => getIndicatorsByCategory(), []);

  // Get all indicators from registry (RSI, MA, EMA, Volume, SR, etc.)
  const availableIndicators = useMemo(() => {
    return INDICATOR_REGISTRY;
  }, []);

  // Filter indicators based on search and tab
  const filteredIndicators = useMemo(() => {
    let filtered = availableIndicators;

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (ind) =>
          ind.name.toLowerCase().includes(query) ||
          ind.description.toLowerCase().includes(query) ||
          ind.type.toLowerCase().includes(query)
      );
    }

    // Filter by active tab
    if (activeTab !== "All") {
      filtered = filtered.filter((ind) => ind.category === activeTab);
    }

    return filtered;
  }, [availableIndicators, searchQuery, activeTab]);

  // Check if indicator is active
  const isIndicatorActive = (type: IndicatorType) => {
    return activeIndicators.some((ind) => ind.type === type);
  };

  // Handle indicator click
  const handleIndicatorClick = (type: IndicatorType) => {
    if (isIndicatorActive(type)) {
      const indicatorToRemove = activeIndicators.find((ind) => ind.type === type);
      if (indicatorToRemove) {
        onRemoveIndicator(indicatorToRemove.id);
      }
    } else {
      onAddIndicator(type);
    }
  };

  return (
    <SimpleModal
      isOpen={open}
      onClose={() => onOpenChange(false)}
      title="Indicators"
      className="max-w-2xl max-h-[80vh] flex flex-col"
    >
      <div className="space-y-4 flex-1 overflow-hidden flex flex-col">
        {/* Simple Search Input */}
        <input
          type="text"
          placeholder="Search indicators..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full px-3 py-2 bg-muted border border-border rounded-md text-sm focus:outline-none"
        />

        {/* Simple Tabs */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Tab Buttons */}
          <div className="flex gap-1 border-b border-border">
            <button
              onClick={() => setActiveTab("All")}
              className={cn(
                "px-4 py-2 text-sm font-medium transition-colors",
                activeTab === "All"
                  ? "text-foreground border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              All
            </button>
            {Object.keys(categories).map((cat) => (
              <button
                key={cat}
                onClick={() => setActiveTab(cat)}
                className={cn(
                  "px-4 py-2 text-sm font-medium transition-colors",
                  activeTab === cat
                    ? "text-foreground border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto mt-4">
            <div className="space-y-1">
              {filteredIndicators.length > 0 ? (
                filteredIndicators.map((indicator) => {
                  const isActive = isIndicatorActive(indicator.type);
                  return (
                    <div
                      key={indicator.type}
                      onClick={() => handleIndicatorClick(indicator.type)}
                      className={cn(
                        "flex items-center justify-between p-2 cursor-pointer hover:bg-muted",
                        isActive && "bg-primary/10"
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{indicator.name}</span>
                        {indicator.requiresSeparatePane && (
                          <span className="text-xs text-muted-foreground">
                            (Pane)
                          </span>
                        )}
                      </div>
                      {isActive && (
                        <span className="text-xs text-primary">Active</span>
                      )}
                    </div>
                  );
                })
              ) : (
                <div className="text-sm text-muted-foreground text-center py-8">
                  No indicators found
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </SimpleModal>
  );
}

