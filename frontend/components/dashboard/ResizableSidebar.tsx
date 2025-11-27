"use client";

import { useState, useRef, useEffect, useCallback, ReactNode } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

const SYMBOL_MANAGER_WIDTH_KEY = "symbol_manager_width";
const SYMBOL_MANAGER_COLLAPSED_KEY = "symbol_manager_collapsed";
const DEFAULT_SIDEBAR_WIDTH = 320;
const MIN_SIDEBAR_WIDTH = 240;
const MAX_SIDEBAR_WIDTH = 600;
const COLLAPSED_WIDTH = 0;

interface ResizableSidebarProps {
  children: ReactNode;
}

export function ResizableSidebar({ children }: ResizableSidebarProps) {
  const [sidebarWidth, setSidebarWidth] = useState<number>(DEFAULT_SIDEBAR_WIDTH);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const [isHydrated, setIsHydrated] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const resizeStartX = useRef<number>(0);
  const resizeStartWidth = useRef<number>(0);

  // Load width and collapsed state from localStorage after hydration
  useEffect(() => {
    setIsHydrated(true);
    if (typeof window !== "undefined") {
      const storedWidth = localStorage.getItem(SYMBOL_MANAGER_WIDTH_KEY);
      const storedCollapsed = localStorage.getItem(SYMBOL_MANAGER_COLLAPSED_KEY);
      
      if (storedWidth) {
        const width = parseInt(storedWidth, 10);
        const clampedWidth = Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, width));
        setSidebarWidth(clampedWidth);
      }
      
      if (storedCollapsed === "true") {
        setIsCollapsed(true);
      }
    }
  }, []);

  // Persist width and collapsed state to localStorage
  useEffect(() => {
    if (isHydrated && typeof window !== "undefined") {
      localStorage.setItem(SYMBOL_MANAGER_WIDTH_KEY, sidebarWidth.toString());
      localStorage.setItem(SYMBOL_MANAGER_COLLAPSED_KEY, isCollapsed.toString());
    }
  }, [sidebarWidth, isCollapsed, isHydrated]);

  // Handle collapse toggle
  const handleToggleCollapse = useCallback(() => {
    setIsCollapsed((prev) => !prev);
  }, []);

  // Handle resize start
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    if (isCollapsed) return;
    e.preventDefault();
    setIsResizing(true);
    resizeStartX.current = e.clientX;
    resizeStartWidth.current = sidebarWidth;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [sidebarWidth, isCollapsed]);

  // Handle resize
  useEffect(() => {
    if (!isResizing || isCollapsed) return;

    const handleMouseMove = (e: MouseEvent) => {
      const deltaX = e.clientX - resizeStartX.current;
      const newWidth = Math.max(
        MIN_SIDEBAR_WIDTH,
        Math.min(MAX_SIDEBAR_WIDTH, resizeStartWidth.current + deltaX)
      );
      setSidebarWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isResizing]);

  // Handle window resize for responsiveness
  useEffect(() => {
    const handleResize = () => {
      if (typeof window !== "undefined" && sidebarRef.current && !isCollapsed) {
        const maxWidth = window.innerWidth * 0.5;
        if (sidebarWidth > maxWidth) {
          setSidebarWidth(Math.min(maxWidth, MAX_SIDEBAR_WIDTH));
        }
      }
    };

    window.addEventListener("resize", handleResize);
    handleResize();

    return () => window.removeEventListener("resize", handleResize);
  }, [sidebarWidth, isCollapsed]);

  const currentWidth = isCollapsed ? COLLAPSED_WIDTH : sidebarWidth;

  return (
    <>
      <div
        ref={sidebarRef}
        className="flex-shrink-0 border-r border-border overflow-hidden relative transition-all duration-200"
        style={{ width: `${currentWidth}px` }}
      >
        {!isCollapsed && (
          <div className="absolute top-2 right-2 z-10">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleToggleCollapse}
              className="h-7 w-7 p-0 hover:bg-muted"
              title="Collapse sidebar"
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </div>
        )}
        {!isCollapsed && <div className="h-full overflow-hidden">{children}</div>}
      </div>
      {!isCollapsed && (
        <div
          className="flex-shrink-0 w-1 bg-border hover:bg-primary/50 cursor-col-resize transition-colors relative group"
          onMouseDown={handleResizeStart}
        >
          <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-2" />
          {isResizing && <div className="absolute inset-0 bg-primary/30" />}
        </div>
      )}
      {isCollapsed && (
        <div className="flex-shrink-0 border-r border-border">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleToggleCollapse}
            className="h-full w-8 p-0 hover:bg-muted rounded-none"
            title="Expand sidebar"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </>
  );
}

