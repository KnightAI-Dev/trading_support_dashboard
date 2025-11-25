"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { LayoutDashboard, Table2, Settings, TrendingUp, Coins } from "lucide-react";

const navigation = [
  { name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { name: "Symbols", href: "/symbols", icon: Coins },
  { name: "Signals", href: "/signals", icon: Table2 },
  { name: "Settings", href: "/settings", icon: Settings },
];

export function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="border-b bg-card">
      <div className="max-w-[1920px] mx-auto px-4 md:px-6">
        <div className="flex items-center gap-1">
          <Link
            href="/dashboard"
            className="flex items-center gap-2 px-3 py-3 text-sm font-medium hover:text-foreground transition-colors"
          >
            <TrendingUp className="h-5 w-5" />
            <span className="hidden sm:inline">Trading Dashboard</span>
          </Link>
          <div className="flex-1" />
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors",
                  isActive
                    ? "text-foreground border-b-2 border-primary"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}

