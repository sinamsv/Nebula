"use client";

import { useEffect, useState } from "react";
import { Moon, Sun, Sparkles, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

const THEMES = [
  { id: "theme-nebula", name: "Nebula", description: "Default branded look with dark purple glow", icon: <Sparkles className="h-5 w-5" /> },
  { id: "theme-dark", name: "Dark", description: "Minimal, dark-mode styling", icon: <Moon className="h-5 w-5" /> },
  { id: "theme-light", name: "Light", description: "Minimal, clean light-mode styling", icon: <Sun className="h-5 w-5" /> },
];

export default function SettingsPage() {
  const [activeTheme, setActiveTheme] = useState("theme-nebula");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("nebula_theme") || "theme-nebula";
      setActiveTheme(saved);
    } catch {}
  }, []);

  function handleSelectTheme(themeId: string) {
    setActiveTheme(themeId);
    try {
      localStorage.setItem("nebula_theme", themeId);
      document.documentElement.className = themeId;
    } catch {}
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 sm:px-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-nebula-purple/10 text-nebula-purple">
          <Settings className="h-5 w-5" />
        </div>
        <div>
          <h1 className="font-display text-2xl font-semibold">Settings</h1>
          <p className="text-sm text-nebula-text-secondary">Customize your Nebula web experience.</p>
        </div>
      </div>

      <div className="mt-8">
        <h2 className="text-base font-semibold text-nebula-text">Visual Theme</h2>
        <p className="text-xs text-nebula-text-secondary mt-1">Select a color scheme that matches your workspace.</p>

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {THEMES.map((t) => (
            <button
              key={t.id}
              onClick={() => handleSelectTheme(t.id)}
              className={cn(
                "flex flex-col gap-3 rounded-2xl border p-5 text-left transition-colors cursor-pointer",
                activeTheme === t.id
                  ? "border-nebula-purple bg-nebula-purple/10 text-nebula-text"
                  : "border-nebula-border bg-white/[0.03] text-nebula-text-secondary hover:bg-white/[0.06] hover:text-nebula-text"
              )}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/5">
                {t.icon}
              </div>
              <div>
                <p className="font-medium text-sm">{t.name}</p>
                <p className="text-[11px] text-nebula-text-secondary mt-1 leading-normal">{t.description}</p>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
