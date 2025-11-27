"use client";

import { useState, useMemo, useCallback, useDeferredValue } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { INDICATOR_REGISTRY, getIndicatorsByCategory } from "@/lib/indicators";
import { IndicatorConfig, IndicatorType } from "@/lib/types";
import { Search, Plus, X } from "lucide-react";

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
  const deferredQuery = useDeferredValue(searchQuery);

  // Memoize categories - only recalculate if INDICATOR_REGISTRY changes
  const categories = useMemo(() => getIndicatorsByCategory(), []);

  // Memoize active indicator types as a Set for O(1) lookup
  const activeTypes = useMemo(
    () => new Set(activeIndicators.map((ind) => ind.type)),
    [activeIndicators]
  );

  // Memoize filtered indicators
  const filteredIndicators = useMemo(() => {
    if (!deferredQuery) return INDICATOR_REGISTRY;
    const query = deferredQuery.toLowerCase();
    return INDICATOR_REGISTRY.filter(
      (ind) =>
        ind.name.toLowerCase().includes(query) ||
        ind.description.toLowerCase().includes(query) ||
        ind.category.toLowerCase().includes(query)
    );
  }, [deferredQuery]);

  // Memoize indicators for current tab
  const currentTabIndicators = useMemo(() => {
    if (activeTab === "All") {
      return filteredIndicators;
    }
    return filteredIndicators.filter((ind) => ind.category === activeTab);
  }, [activeTab, filteredIndicators]);

  // Memoize click handler
  const handleIndicatorClick = useCallback(
    (indicator: typeof INDICATOR_REGISTRY[0]) => {
      const isActive = activeTypes.has(indicator.type);
      if (isActive) {
        const indicatorToRemove = activeIndicators.find(
          (ind) => ind.type === indicator.type
        );
        if (indicatorToRemove) {
          onRemoveIndicator(indicatorToRemove.id);
        }
      } else {
        onAddIndicator(indicator.type);
      }
    },
    [activeTypes, activeIndicators, onAddIndicator, onRemoveIndicator]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Indicators</DialogTitle>
          <DialogDescription>
            Add technical indicators to your chart
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 flex-1 overflow-hidden flex flex-col">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search indicators..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Categories Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 overflow-hidden flex flex-col">
            <TabsList className="grid w-full grid-cols-5">
              <TabsTrigger value="All">All</TabsTrigger>
              {Object.keys(categories).map((cat) => (
                <TabsTrigger key={cat} value={cat}>
                  {cat}
                </TabsTrigger>
              ))}
            </TabsList>

            <div className="flex-1 overflow-y-auto mt-4">
              {/* Only render the active tab content */}
              <TabsContent value={activeTab} className="mt-0">
                <div className="grid gap-2">
                  {currentTabIndicators.map((indicator) => {
                    const isActive = activeTypes.has(indicator.type);
                    return (
                      <div
                        key={indicator.type}
                        className="flex items-center justify-between p-3 border rounded-lg hover:bg-accent transition-colors"
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium">{indicator.name}</h4>
                            {indicator.requiresSeparatePane && (
                              <Badge variant="secondary" className="text-xs">
                                Separate Pane
                              </Badge>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {indicator.description}
                          </p>
                        </div>
                        <Button
                          variant={isActive ? "destructive" : "default"}
                          size="sm"
                          onClick={() => handleIndicatorClick(indicator)}
                        >
                          {isActive ? (
                            <>
                              <X className="h-4 w-4 mr-1" />
                              Remove
                            </>
                          ) : (
                            <>
                              <Plus className="h-4 w-4 mr-1" />
                              Add
                            </>
                          )}
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
}

