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
        // Exact Nebula palette, confirmed by Sina. Referenced as
        // bg-nebula-pink, text-nebula-purple, etc. throughout.
        "nebula-bg": "#09090B",
        "nebula-bg-secondary": "#111217",
        "nebula-pink": "#FF5CA8",
        "nebula-purple": "#9D4EDD",
        "nebula-blue": "#53B9FF",
        "nebula-text": "#F5F5F5",
        "nebula-text-secondary": "#A0A0A0",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "nebula-glow": "radial-gradient(circle at 20% 20%, rgba(157,78,221,0.18), transparent 45%), radial-gradient(circle at 80% 0%, rgba(83,185,255,0.14), transparent 40%), radial-gradient(circle at 50% 100%, rgba(255,92,168,0.12), transparent 45%)",
      },
      boxShadow: {
        glow: "0 0 40px -10px rgba(157, 78, 221, 0.35)",
        "glow-pink": "0 0 40px -10px rgba(255, 92, 168, 0.35)",
        "glow-blue": "0 0 40px -10px rgba(83, 185, 255, 0.35)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
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
      },
      animation: {
        "fade-in": "fade-in 0.25s ease-out",
        "pulse-dot": "pulse-dot 1.4s infinite ease-in-out",
        "drift-slow": "drift 18s infinite ease-in-out",
        "drift-slower": "drift 26s infinite ease-in-out",
      },
    },
  },
  plugins: [],
};

export default config;
