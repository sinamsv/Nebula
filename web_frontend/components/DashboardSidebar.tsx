"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  PanelLeftClose,
  PanelLeftOpen,
  Sparkles,
  Radio,
  BookOpen,
  FolderKanban,
  Wrench,
  KeyRound,
  ShieldCheck,
  LogOut,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

export interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  comingSoon?: boolean;
}

export const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard/playground", label: "Playground", icon: <Sparkles className="h-4 w-4" /> },
  { href: "/dashboard/platforms", label: "Platforms", icon: <Radio className="h-4 w-4" /> },
  { href: "/dashboard/docs", label: "Docs", icon: <BookOpen className="h-4 w-4" /> },
  { href: "/dashboard/projects", label: "Projects", icon: <FolderKanban className="h-4 w-4" />, comingSoon: true },
  { href: "/dashboard/tools", label: "Tools", icon: <Wrench className="h-4 w-4" />, comingSoon: true },
  { href: "/dashboard/api-key", label: "API key", icon: <KeyRound className="h-4 w-4" />, comingSoon: true },
];

interface DashboardSidebarProps {
  /** True = full width with labels, false = icon rail only. Desktop only -- ignored on mobile, which is always full width when open. */
  collapsed: boolean;
  onToggleCollapsed: () => void;
  /** Mobile full-screen panel open/closed. Irrelevant on desktop. */
  mobileOpen: boolean;
  onCloseMobile: () => void;
  isAdmin: boolean;
  username: string | null;
  onLogout: () => void;
}

/**
 * The single nav surface for the whole dashboard, used two ways:
 *  - Desktop (md+): a permanently docked column, collapsible between
 *    an icon-only rail and a full labeled sidebar (Claude/ChatGPT-style).
 *  - Mobile: a full-screen panel that slides in, rather than the old
 *    partial-width drawer -- opened via a small button in the top bar.
 *
 * Kept as ONE component (not two separate ones) so nav items, admin
 * link, and logout button never drift out of sync between the two
 * breakpoints.
 */
export default function DashboardSidebar({
  collapsed,
  onToggleCollapsed,
  mobileOpen,
  onCloseMobile,
  isAdmin,
  username,
  onLogout,
}: DashboardSidebarProps) {
  const pathname = usePathname();

  const items = (
    <>
      {NAV_ITEMS.map((item) => {
        const isActive = pathname?.startsWith(item.href);
        if (item.comingSoon) {
          return (
            <div
              key={item.href}
              title={collapsed ? `${item.label} (coming soon)` : undefined}
              className={cn(
                "flex cursor-not-allowed items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-nebula-text-secondary/40",
                collapsed && "justify-center px-0"
              )}
            >
              {item.icon}
              {!collapsed ? (
                <>
                  <span className="flex-1">{item.label}</span>
                  <span className="rounded-full bg-white/5 px-1.5 py-0.5 text-[10px]">soon</span>
                </>
              ) : null}
            </div>
          );
        }
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onCloseMobile}
            title={collapsed ? item.label : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
              collapsed && "justify-center px-0",
              isActive
                ? "bg-nebula-purple/15 text-nebula-purple"
                : "text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text"
            )}
          >
            {item.icon}
            {!collapsed ? <span>{item.label}</span> : null}
          </Link>
        );
      })}

      {isAdmin ? (
        <>
          <div className="my-2 h-px bg-white/10" />
          {!collapsed ? (
            <span className="px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-nebula-text-secondary/60">
              Admin
            </span>
          ) : null}
          <Link
            href="/dashboard/admin"
            onClick={onCloseMobile}
            title={collapsed ? "Admin panel" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors",
              collapsed && "justify-center px-0",
              pathname?.startsWith("/dashboard/admin")
                ? "bg-nebula-purple/15 text-nebula-purple"
                : "text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text"
            )}
          >
            <ShieldCheck className="h-4 w-4" />
            {!collapsed ? <span>Admin panel</span> : null}
          </Link>
        </>
      ) : null}
    </>
  );

  const footer = (
    <div className={cn("flex items-center gap-2 border-t border-white/10 pt-3", collapsed && "flex-col")}>
      {!collapsed ? (
        <span className="min-w-0 flex-1 truncate text-xs text-nebula-text-secondary">{username ?? "..."}</span>
      ) : null}
      <button
        onClick={onLogout}
        title="Log out"
        className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-nebula-text-secondary transition-colors hover:bg-white/5 hover:text-red-300"
      >
        <LogOut className="h-4 w-4" />
      </button>
    </div>
  );

  return (
    <>
      {/* Desktop: permanently docked column, width animates between rail/full */}
      <aside
        className={cn(
          "hidden flex-shrink-0 flex-col gap-1 border-r border-white/5 bg-nebula-bg-secondary/40 p-3 transition-[width] duration-200 md:flex",
          collapsed ? "w-[68px]" : "w-64"
        )}
      >
        <div className={cn("mb-2 flex items-center gap-2", collapsed ? "justify-center" : "justify-between")}>
          {!collapsed ? (
            <Link href="/dashboard/playground" className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-nebula-purple to-nebula-pink">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <span className="font-display text-sm font-semibold">Nebula</span>
            </Link>
          ) : (
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-nebula-purple to-nebula-pink">
              <Bot className="h-4 w-4 text-white" />
            </div>
          )}
        </div>

        <button
          onClick={onToggleCollapsed}
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "mb-2 flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-xs text-nebula-text-secondary transition-colors hover:bg-white/5 hover:text-nebula-text",
            collapsed && "justify-center px-0"
          )}
        >
          {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          {!collapsed ? <span>Collapse</span> : null}
        </button>

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">{items}</nav>

        {footer}
      </aside>

      {/* Mobile: full-screen panel (not a partial drawer) */}
      {mobileOpen ? (
        <div className="fixed inset-0 z-40 flex flex-col bg-nebula-bg p-4 md:hidden">
          <div className="mb-4 flex items-center justify-between">
            <Link href="/dashboard/playground" onClick={onCloseMobile} className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-nebula-purple to-nebula-pink">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <span className="font-display text-sm font-semibold">Nebula</span>
            </Link>
            <button
              onClick={onCloseMobile}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text"
              aria-label="Close menu"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <nav className="flex flex-1 flex-col gap-1 overflow-y-auto">{items}</nav>

          {footer}
        </div>
      ) : null}
    </>
  );
}
