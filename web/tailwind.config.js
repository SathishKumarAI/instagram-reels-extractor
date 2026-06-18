/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Catppuccin Mocha
        base: "#1e1e2e",
        mantle: "#181825",
        crust: "#11111b",
        surface0: "#313244",
        surface1: "#45475a",
        surface2: "#585b70",
        overlay0: "#6c7086",
        text: "#cdd6f4",
        subtext: "#a6adc8",
        mauve: "#cba6f7",
        blue: "#89b4fa",
        sapphire: "#74c7ec",
        green: "#a6e3a1",
        yellow: "#f9e2af",
        peach: "#fab387",
        red: "#f38ba8",
        pink: "#f5c2e7",
      },
      borderRadius: { lg: "0.75rem", xl: "1rem" },
    },
  },
  plugins: [],
};
