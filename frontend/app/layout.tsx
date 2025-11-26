import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/client/Navigation";
import { WebSocketProvider } from "@/components/client/WebSocketProvider";
import { ErrorBoundary } from "@/components/error/ErrorBoundary";

const inter = Inter({ 
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Trading Support Dashboard",
  description: "Real-time crypto market structure analysis and trading signals",
  icons: {
    icon: "/icon.svg",
    shortcut: "/icon.svg",
    apple: "/icon.svg",
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

