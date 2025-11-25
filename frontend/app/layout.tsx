import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/client/Navigation";
import { WebSocketProvider } from "@/components/client/WebSocketProvider";

const inter = Inter({ 
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Trading Support Dashboard",
  description: "Real-time crypto market structure analysis and trading signals",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={inter.className}>
        <Navigation />
        <WebSocketProvider>
          {children}
        </WebSocketProvider>
      </body>
    </html>
  );
}

