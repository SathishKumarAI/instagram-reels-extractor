/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class", '[data-mode="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Catppuccin/Databricks palette via CSS variables → theme-swappable.
        // Values live in src/index.css :root / [data-theme]. Ported from prepforge.
        base: "rgb(var(--ctp-base) / <alpha-value>)",
        mantle: "rgb(var(--ctp-mantle) / <alpha-value>)",
        crust: "rgb(var(--ctp-crust) / <alpha-value>)",
        surface0: "rgb(var(--ctp-surface0) / <alpha-value>)",
        surface1: "rgb(var(--ctp-surface1) / <alpha-value>)",
        surface2: "rgb(var(--ctp-surface2) / <alpha-value>)",
        overlay0: "rgb(var(--ctp-overlay0) / <alpha-value>)",
        overlay1: "rgb(var(--ctp-overlay1) / <alpha-value>)",
        // reels uses singular `subtext`; keep it + expose 0/1 too
        subtext: "rgb(var(--ctp-subtext0) / <alpha-value>)",
        subtext0: "rgb(var(--ctp-subtext0) / <alpha-value>)",
        subtext1: "rgb(var(--ctp-subtext1) / <alpha-value>)",
        text: "rgb(var(--ctp-text) / <alpha-value>)",
        rosewater: "rgb(var(--ctp-rosewater) / <alpha-value>)",
        flamingo: "rgb(var(--ctp-flamingo) / <alpha-value>)",
        pink: "rgb(var(--ctp-pink) / <alpha-value>)",
        mauve: "rgb(var(--ctp-mauve) / <alpha-value>)",
        red: "rgb(var(--ctp-red) / <alpha-value>)",
        maroon: "rgb(var(--ctp-maroon) / <alpha-value>)",
        peach: "rgb(var(--ctp-peach) / <alpha-value>)",
        yellow: "rgb(var(--ctp-yellow) / <alpha-value>)",
        green: "rgb(var(--ctp-green) / <alpha-value>)",
        teal: "rgb(var(--ctp-teal) / <alpha-value>)",
        sky: "rgb(var(--ctp-sky) / <alpha-value>)",
        sapphire: "rgb(var(--ctp-sapphire) / <alpha-value>)",
        blue: "rgb(var(--ctp-blue) / <alpha-value>)",
        lavender: "rgb(var(--ctp-lavender) / <alpha-value>)",
      },
      borderRadius: { lg: "0.75rem", xl: "1rem" },
    },
  },
  plugins: [],
};
