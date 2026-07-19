"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bot,
  Menu,
  X,
  Sparkles,
  Radio,
  BookOpen,
  FolderKanban,
  Wrench,
  KeyRound,
  ShieldCheck,
  LogOut,
  Coins,
} from "lucide-react";
import ProtectedRoute from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/AuthContext";
import { getHealth, getMyCoins, ApiError } from "@/lib/api";
import type { CoinStatusResponse } from "@/types/api";
import { formatDuration, cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  comingSoon?: boolean;
  adminOnly?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard/playground", label: "Playground", icon: <Sparkles className="h-4 w-4" /> },
  { href: "/dashboard/platforms", label: "Platforms", icon: <Radio className="h-4 w-4" /> },
  { href: "/dashboard/docs", label: "Docs", icon: <BookOpen className="h-4 w-4" /> },
  { href: "/dashboard/projects", label: "Projects", icon: <FolderKanban className="h-4 w-4" />, comingSoon: true },
  { href: "/dashboard/tools", label: "Tools", icon: <Wrench className="h-4 w-4" />, comingSoon: true },
  { href: "/dashboard/api-key", label: "API key", icon: <KeyRound className="h-4 w-4" />, comingSoon: true },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <DashboardShell>{children}</DashboardShell>
    </ProtectedRoute>
  );
}

function DashboardShell({ children }: { children: ReactNode }) {
  const { user, token, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const [menuOpen, setMenuOpen] = useState(false);
  const [coins, setCoins] = useState<CoinStatusResponse | null>(null);
  const [aiConfigured, setAiConfigured] = useState(true);
  const [healthChecked, setHealthChecked] = useState(false);

  useEffect(() => {
    getHealth()
      .then((res) => setAiConfigured(res.ai_configured))
      .catch(() => setAiConfigured(true)) // fail open -- don't block UI on a health-check hiccup
      .finally(() => setHealthChecked(true));
  }, []);

  useEffect(() => {
    if (!token) return;
    refreshCoins();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function refreshCoins() {
    if (!token) return;
    try {
      const status = await getMyCoins(token);
      setCoins(status);
    } catch {
      // Non-critical -- header simply omits the balance if this fails.
    }
  }

  function handleLogout() {
    logout();
    router.push("/login");
  }

  return (
    <div className="relative min-h-screen">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-white/5 bg-nebula-bg/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMenuOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-nebula-text-secondary transition-colors hover:bg-white/5 hover:text-nebula-text"
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <Link href="/dashboard/playground" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-nebula-purple to-nebula-pink">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <span className="hidden font-display text-sm font-semibold sm:inline">Nebula</span>
            </Link>
          </div>

          <div className="flex items-center gap-3">
            <CoinBadge coins={coins} />
            <div className="hidden items-center gap-2 sm:flex">
              <span className="text-sm text-nebula-text-secondary">{user?.username ?? "..."}</span>
              {user?.is_admin ? (
                <span className="flex items-center gap-1 rounded-full bg-nebula-purple/15 px-2 py-0.5 text-[11px] font-medium text-nebula-purple">
                  <ShieldCheck className="h-3 w-3" /> Admin
                </span>
              ) : null}
            </div>
            <button
              onClick={handleLogout}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-nebula-text-secondary transition-colors hover:bg-white/5 hover:text-red-300"
              aria-label="Log out"
              title="Log out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>

        {healthChecked && !aiConfigured ? (
          <div className="border-t border-amber-500/20 bg-amber-500/10 px-4 py-2 text-center text-xs text-amber-200 sm:px-6">
            Nebula&apos;s AI isn&apos;t configured yet — contact an admin.
          </div>
        ) : null}

        {user && !user.is_approved ? (
          <div className="border-t border-nebula-blue/20 bg-nebula-blue/10 px-4 py-2 text-center text-xs text-nebula-blue sm:px-6">
            Your account is pending admin approval. You&apos;ll be able to chat with Nebula once approved.
          </div>
        ) : null}
      </header>

      {/* Slide-out nav */}
      {menuOpen ? (
        <div className="fixed inset-0 z-40 flex">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMenuOpen(false)} />
          <nav className="relative flex h-full w-72 flex-col gap-1 border-r border-white/10 bg-nebula-bg-secondary/95 p-4 backdrop-blur-xl animate-fade-in">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-display text-sm font-semibold text-nebula-text-secondary">Menu</span>
              <button
                onClick={() => setMenuOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text"
                aria-label="Close menu"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {NAV_ITEMS.map((item) => {
              const isActive = pathname?.startsWith(item.href);
              if (item.comingSoon) {
                return (
                  <div
                    key={item.href}
                    className="flex cursor-not-allowed items-center justify-between rounded-xl px-3 py-2.5 text-sm text-nebula-text-secondary/40"
                  >
                    <span className="flex items-center gap-2.5">
                      {item.icon}
                      {item.label}
                    </span>
                    <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px]">soon</span>
                  </div>
                );
              }
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMenuOpen(false)}
                  className={cn(
                    "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm transition-colors",
                    isActive
                      ? "bg-nebula-purple/15 text-nebula-purple"
                      : "text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text"
                  )}
                >
                  {item.icon}
                  {item.label}
                </Link>
              );
            })}

            {user?.is_admin ? (
              <>
                <div className="my-2 h-px bg-white/10" />
                <span className="px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-nebula-text-secondary/60">
                  Admin
                </span>
                <Link
                  href="/dashboard/admin"
                  onClick={() => setMenuOpen(false)}
                  className={cn(
                    "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm transition-colors",
                    pathname?.startsWith("/dashboard/admin")
                      ? "bg-nebula-purple/15 text-nebula-purple"
                      : "text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text"
                  )}
                >
                  <ShieldCheck className="h-4 w-4" />
                  Admin panel
                </Link>
              </>
            ) : null}
          </nav>
        </div>
      ) : null}

      <div className="mx-auto max-w-7xl">{children}</div>
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
      className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs"
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
