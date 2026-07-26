"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronDown, Bot, Check } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Purely visual model selector for the composer. Always displays
 * "Nebula" and does not affect which backend model actually serves
 * the request -- the backend's provider/model selection is entirely
 * server-side (see ai/providers/*), and this control doesn't call any
 * API. It exists only so the composer reads like a real chat product;
 * wiring it to an actual model-switch endpoint is future work, not
 * part of this pass.
 */
export default function ModelSelector() {
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

  return (
    <div ref={containerRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-nebula-text-secondary transition-colors hover:bg-white/[0.06] hover:text-nebula-text cursor-pointer"
      >
        <Bot className="h-3.5 w-3.5 text-nebula-purple" />
        <span>Nebula</span>
        <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
      </button>

      {open ? (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-56 rounded-xl border border-nebula-border bg-nebula-surface/95 p-1.5 shadow-glow-soft backdrop-blur-xl animate-scale-in">
          <button
            onClick={() => setOpen(false)}
            className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm text-nebula-text transition-colors hover:bg-white/5 cursor-pointer"
          >
            <span className="flex items-center gap-2">
              <Bot className="h-3.5 w-3.5 text-nebula-purple" />
              Nebula
            </span>
            <Check className="h-3.5 w-3.5 text-nebula-purple" />
          </button>
        </div>
      ) : null}
    </div>
  );
}
