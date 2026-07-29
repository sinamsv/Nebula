"use client";

import { useEffect, useRef, useState } from "react";
import { Plus, ImageIcon, Search, Sparkles, SearchX, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { SearchMode } from "@/types/api";

interface PlusMenuProps {
  onPickImage: () => void;
  searchMode: SearchMode;
  onSearchModeChange: (mode: SearchMode) => void;
  disabled?: boolean;
}

const SEARCH_OPTIONS: { mode: SearchMode; label: string; description: string; icon: typeof Search }[] = [
  { mode: "on", label: "Search: On", description: "Always search the web when useful", icon: Search },
  { mode: "smart", label: "Search: Smart", description: "Nebula decides for itself", icon: Sparkles },
  { mode: "off", label: "Search: Off", description: "Never search the web", icon: SearchX },
];

/**
 * The composer's "+" button -- opens a small popover with two things:
 * a file-upload trigger (delegates to the same hidden <input type=file>
 * flow MessageInput already had) and the search-mode toggle (same
 * three states as the old standalone SearchModeButton, just relocated
 * here so the "+" is the single entry point for composer tools, matching
 * the ChatGPT/Claude pattern). No new backend behavior -- purely a
 * UI reorganization of controls that already existed.
 */
export default function PlusMenu({ onPickImage, searchMode, onSearchModeChange, disabled }: PlusMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const activeSearchConfig = SEARCH_OPTIONS.find((o) => o.mode === searchMode)!;

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={disabled}
        title="Add photos or tools"
        className={cn(
          "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full border transition-all cursor-pointer disabled:cursor-not-allowed disabled:opacity-50",
          open
            ? "border-nebula-purple/40 bg-nebula-purple/15 text-nebula-purple"
            : "border-transparent text-nebula-text-secondary hover:bg-white/10 hover:text-nebula-text"
        )}
      >
        <Plus className={cn("h-4 w-4 transition-transform", open && "rotate-45")} />
      </button>

      {open ? (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-64 rounded-xl border border-nebula-border bg-nebula-surface/75 p-1.5 shadow-glow-soft backdrop-blur-xl animate-scale-in">
          <button
            onClick={() => {
              onPickImage();
              setOpen(false);
            }}
            className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left text-sm text-nebula-text transition-colors hover:bg-white/5 cursor-pointer"
          >
            <ImageIcon className="h-4 w-4 text-nebula-blue" />
            <span>Attach an image</span>
          </button>

          <div className="my-1 h-px bg-nebula-border" />

          <p className="px-2.5 pb-1 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-nebula-text-secondary/60">
            Web search
          </p>
          {SEARCH_OPTIONS.map((option) => {
            const Icon = option.icon;
            const isActive = option.mode === searchMode;
            return (
              <button
                key={option.mode}
                onClick={() => {
                  onSearchModeChange(option.mode);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors cursor-pointer",
                  isActive ? "bg-nebula-purple/10 text-nebula-text" : "text-nebula-text-secondary hover:bg-white/5 hover:text-nebula-text"
                )}
              >
                <Icon className={cn("h-4 w-4 flex-shrink-0", isActive ? "text-nebula-purple" : "")} />
                <span className="flex-1">
                  <span className="block">{option.label}</span>
                  <span className="block text-[11px] text-nebula-text-secondary/70">{option.description}</span>
                </span>
                {isActive ? <Check className="h-3.5 w-3.5 flex-shrink-0 text-nebula-purple" /> : null}
              </button>
            );
          })}
        </div>
      ) : null}

      <p className="sr-only" aria-live="polite">
        {activeSearchConfig.label}
      </p>
    </div>
  );
}
