import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Nebula palette -- unchanged brand hues, refined neutrals for
        // clearer surface hierarchy (panel vs. page vs. hover states).
        "nebula-bg": "#09090B",
        "nebula-bg-secondary": "#111217",
        "nebula-surface": "#0D0E13",
        "nebula-surface-hover": "#15161D",
        "nebula-pink": "#FF5CA8",
        "nebula-purple": "#9D4EDD",
        "nebula-blue": "#53B9FF",
        "nebula-text": "#F5F5F5",
        "nebula-text-secondary": "#9A9AA5",
        "nebula-text-tertiary": "#6B6B76",
        "nebula-border": "rgba(255,255,255,0.08)",
        "nebula-border-hover": "rgba(255,255,255,0.16)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "nebula-glow": "radial-gradient(circle at 20% 20%, rgba(157,78,221,0.18), transparent 45%), radial-gradient(circle at 80% 0%, rgba(83,185,255,0.14), transparent 40%), radial-gradient(circle at 50% 100%, rgba(255,92,168,0.12), transparent 45%)",
        "nebula-text-gradient": "linear-gradient(90deg, #FF5CA8 0%, #9D4EDD 50%, #53B9FF 100%)",
      },
      boxShadow: {
        glow: "0 0 40px -10px rgba(157, 78, 221, 0.35)",
        "glow-pink": "0 0 40px -10px rgba(255, 92, 168, 0.35)",
        "glow-blue": "0 0 40px -10px rgba(83, 185, 255, 0.35)",
        "glow-soft": "0 8px 30px -8px rgba(0, 0, 0, 0.5)",
        "composer": "0 -8px 40px -16px rgba(157, 78, 221, 0.25), 0 4px 24px -4px rgba(0,0,0,0.4)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "scale-in": {
          "0%": { opacity: "0", transform: "scale(0.97)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
        "pulse-dot": {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
        "drift": {
          "0%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(-2%, 3%) scale(1.05)" },
          "100%": { transform: "translate(0, 0) scale(1)" },
        },
        "shimmer": {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
        "fade-in-up": "fade-in-up 0.45s cubic-bezier(0.16, 1, 0.3, 1)",
        "scale-in": "scale-in 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        "pulse-dot": "pulse-dot 1.4s infinite ease-in-out",
        "drift-slow": "drift 18s infinite ease-in-out",
        "drift-slower": "drift 26s infinite ease-in-out",
        "shimmer": "shimmer 3s linear infinite",
      },
      transitionTimingFunction: {
        "composer": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
