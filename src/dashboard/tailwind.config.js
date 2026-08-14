/** Design tokens from the merge-cockpit handoff. */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "oklch(0.145 0.01 255)",
        rail: "oklch(0.165 0.01 255)",
        card: "oklch(0.195 0.012 255)",
        raised: "oklch(0.205 0.012 255)",
        "line-dim": "oklch(0.23 0.011 255)",
        line: "oklch(0.27 0.013 255)",
        "line-strong": "oklch(0.31 0.015 255)",
        ink: "oklch(0.93 0.008 255)",
        body: "oklch(0.88 0.008 255)",
        muted: "oklch(0.68 0.012 255)",
        dim: "oklch(0.58 0.012 255)",
        faint: "oklch(0.47 0.012 255)",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Helvetica",
          "Arial",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      keyframes: {
        apronIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "none" },
        },
        apronPulse: {
          "0%,100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.35", transform: "scale(0.82)" },
        },
      },
      animation: {
        "in-card": "apronIn 260ms ease both",
        "in-row": "apronIn 220ms ease both",
        "pulse-dot": "apronPulse 1.6s ease-in-out infinite",
        "pulse-slow": "apronPulse 2.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
