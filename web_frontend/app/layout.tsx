import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { AuthProvider } from "@/lib/AuthContext";
import { CoinsProvider } from "@/lib/CoinsContext";
import NebulaBackground from "@/components/NebulaBackground";

export const metadata: Metadata = {
  title: "Nebula — Your AI, everywhere you already are",
  description:
    "Nebula is an AI assistant reachable from Discord, Telegram, and the web — one account, one memory, one coin balance, wherever you talk to it from.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">
        <NebulaBackground />
        <AuthProvider>
          <CoinsProvider>{children}</CoinsProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
