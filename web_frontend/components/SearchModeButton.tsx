"use client";

import { Search, Sparkles, SearchX } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SearchMode } from "@/types/api";

interface SearchModeButtonProps {
  mode: SearchMode;
  onChange: (mode: SearchMode) => void;
  disabled?: boolean;
}

// Cycle order: on -> smart -> off -> on -> ...
// "smart" sits in the middle since it's the default a user lands back
// on most naturally after experimenting with the other two.
const NEXT_MODE: Record<SearchMode, SearchMode> = {
  on: "smart",
  smart: "off",
  off: "on",
};

const MODE_CONFIG: Record<
  SearchMode,
  { label: string; icon: typeof Search; activeClass: string; title: string }
> = {
  on: {
    label: "On",
    icon: Search,
    activeClass: "border-nebula-blue/40 bg-nebula-blue/15 text-nebula-blue",
    title: "Search: On — Nebula will search whenever your message could use it. Click to switch to Smart.",
  },
  smart: {
    label: "Smart",
    icon: Sparkles,
    activeClass: "border-nebula-purple/40 bg-nebula-purple/15 text-nebula-purple",
    title: "Search: Smart (default) — Nebula decides for itself when a search is needed. Click to switch to Off.",
  },
  off: {
    label: "Off",
    icon: SearchX,
    activeClass: "border-white/10 bg-white/5 text-nebula-text-secondary",
    title: "Search: Off — Nebula will never search. Click to switch to On.",
  },
};

/** A single button that cycles through the three search modes on
 * click (on -> smart -> off -> on -> ...), rather than a dropdown --
 * confirmed as the preferred UI with Sina: fastest to reach any state
 * with a click or two, and the icon+label makes the current mode
 * unambiguous at a glance without opening anything. */
export default function SearchModeButton({ mode, onChange, disabled }: SearchModeButtonProps) {
  const config = MODE_CONFIG[mode];
  const Icon = config.icon;

  return (
    <button
      onClick={() => onChange(NEXT_MODE[mode])}
      disabled={disabled}
      title={config.title}
      className={cn(
        "flex h-10 flex-shrink-0 items-center gap-1.5 rounded-xl border px-3 text-xs font-medium transition-colors cursor-pointer disabled:cursor-not-allowed disabled:opacity-50",
        config.activeClass
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">Search: {config.label}</span>
      <span className="sm:hidden">{config.label}</span>
    </button>
  );
}
