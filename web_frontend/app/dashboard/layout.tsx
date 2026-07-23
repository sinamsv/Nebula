"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Menu, ShieldCheck, Coins } from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import DashboardSidebar from "@/components/DashboardSidebar";
import { useAuth } from "@/lib/AuthContext";
import { useCoins } from "@/lib/CoinsContext";
import { getHealth } from "@/lib/api";
import { formatDuration } from "@/lib/utils";
import type { CoinStatusResponse } from "@/types/api";

const SIDEBAR_COLLAPSED_KEY = "nebula_sidebar_collapsed";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <DashboardShell>{children}</DashboardShell>
    </ProtectedRoute>
  );
}

function DashboardShell({ children }: { children: ReactNode }) {
  const { user, token, logout } = useAuth();
  const { coins, refreshCoins } = useCoins();
  const router = useRouter();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  // Defaults to expanded; the actual saved preference is read after
  // mount (see effect below) since localStorage doesn't exist during
  // server-side rendering -- reading it any earlier would either
  // crash on the server or cause a hydration mismatch.
  const [collapsed, setCollapsed] = useState(false);
  const [aiConfigured, setAiConfigured] = useState(true);
  const [healthChecked, setHealthChecked] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
      if (saved === "1") setCollapsed(true);
    } catch {
      // Storage unavailable -- fall back to the expanded default.
    }
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        // no-op -- preference just won't persist across reloads
      }
      return next;
    });
  }

  useEffect(() => {
    getHealth()
      .then((res) => setAiConfigured(res.ai_configured))
      .catch(() => setAiConfigured(true))
      .finally(() => setHealthChecked(true));
  }, []);

  useEffect(() => {
    if (!token) return;
    refreshCoins(token);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <DashboardSidebar
        collapsed={collapsed}
        onToggleCollapsed={toggleCollapsed}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
        isAdmin={!!user?.is_admin}
        username={user?.username ?? null}
        onLogout={handleLogout}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Slim top bar -- just the mobile menu trigger, admin badge, and coin balance.
            No page title here on purpose: each page owns its own heading, same as
            Claude's chat title living inside the conversation column, not a global bar. */}
        <header className="flex flex-shrink-0 items-center justify-between border-b border-white/5 px-4 py-2.5 sm:px-6">
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-nebula-text-secondary transition-colors hover:bg-white/5 hover:text-nebula-text md:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="hidden md:block" />

          <div className="flex items-center gap-3">
            <CoinBadge coins={coins} />
            {user?.is_admin ? (
              <span className="hidden items-center gap-1 rounded-full bg-nebula-purple/15 px-2 py-0.5 text-[11px] font-medium text-nebula-purple sm:flex">
                <ShieldCheck className="h-3 w-3" /> Admin
              </span>
            ) : null}
          </div>
        </header>

        {healthChecked && !aiConfigured ? (
          <div className="flex-shrink-0 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-200 sm:px-6">
            Nebula&apos;s AI isn&apos;t configured yet — contact an admin.
          </div>
        ) : null}

        {user && !user.is_approved ? (
          <div className="flex-shrink-0 border-b border-nebula-blue/20 bg-nebula-blue/10 px-4 py-2 text-center text-xs text-nebula-blue sm:px-6">
            Your account is pending admin approval. You&apos;ll be able to chat with Nebula once approved.
          </div>
        ) : null}

        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

function CoinBadge({ coins }: { coins: CoinStatusResponse | null }) {
  if (!coins) {
    return (
      <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-nebula-text-secondary">
        <Coins className="h-3.5 w-3.5" />
        <span>...</span>
      </div>
    );
  }
  return (
    <div
      className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs animate-fade-in"
      title={`Resets in ${formatDuration(coins.seconds_until_reset)}`}
    >
      <Coins className="h-3.5 w-3.5 text-nebula-pink" />
      <span className="font-medium text-nebula-text">{coins.balance}</span>
      <span className="hidden text-nebula-text-secondary sm:inline">
        · resets in {formatDuration(coins.seconds_until_reset)}
      </span>
    </div>
  );
}
