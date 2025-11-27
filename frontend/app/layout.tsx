import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/client/Navigation";
import { WebSocketProvider } from "@/components/client/WebSocketProvider";
import { ErrorBoundary } from "@/components/error/ErrorBoundary";

const inter = Inter({ 
  subsets: ["latin"],
  display: "swap",
  fallback: ["system-ui", "arial"], // Explicit fallback fonts
  adjustFontFallback: true, // Better fallback handling
  preload: false, // Disable preload to avoid blocking
});

export const metadata: Metadata = {
  title: "Trading Support Dashboard",
  description: "Real-time crypto market structure analysis and trading signals",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <ErrorBoundary>
          <Navigation />
          <WebSocketProvider>
            <ErrorBoundary>
              {children}
            </ErrorBoundary>
          </WebSocketProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}

