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
        "nebula-bg": "var(--bg-main)",
        "nebula-bg-secondary": "var(--bg-secondary)",
        "nebula-surface": "var(--bg-surface)",
        "nebula-surface-hover": "var(--bg-surface-hover)",
        "nebula-pink": "var(--accent-pink)",
        "nebula-purple": "var(--accent-purple)",
        "nebula-blue": "var(--accent-blue)",
        "nebula-text": "var(--text-main)",
        "nebula-text-secondary": "var(--text-secondary)",
        "nebula-text-tertiary": "var(--text-tertiary)",
        "nebula-border": "var(--border-main)",
        "nebula-border-hover": "var(--border-hover)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      backgroundImage: {
        "nebula-glow": "var(--nebula-glow)",
        "nebula-text-gradient": "linear-gradient(90deg, var(--accent-pink) 0%, var(--accent-purple) 50%, var(--accent-blue) 100%)",
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
