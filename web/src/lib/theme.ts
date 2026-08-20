// Theme application + persistence. Ported from prepforge. Pure DOM side-effects;
// selection persists in localStorage. No settings framework needed.
export type ThemeMode =
  | "mocha"
  | "latte"
  | "databricks-dark"
  | "databricks-light"
  | "system";

const LIGHT_THEMES = new Set(["latte", "databricks-light"]);
const KEY = "reels-theme";

export const THEME_OPTIONS: { value: ThemeMode; label: string }[] = [
  { value: "mocha", label: "Catppuccin dark" },
  { value: "latte", label: "Catppuccin light" },
  { value: "databricks-dark", label: "Databricks dark" },
  { value: "databricks-light", label: "Databricks light" },
  { value: "system", label: "System" },
];

function prefersLight(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: light)").matches;
}

export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  const theme = mode === "system" ? (prefersLight() ? "latte" : "mocha") : mode;
  if (theme === "mocha") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  root.setAttribute("data-mode", LIGHT_THEMES.has(theme) ? "light" : "dark");
}

export function loadTheme(): ThemeMode {
  return (localStorage.getItem(KEY) as ThemeMode) || "mocha";
}

export function saveTheme(mode: ThemeMode): void {
  localStorage.setItem(KEY, mode);
  applyTheme(mode);
}

// call once before React renders so there's no flash of the default theme
export function initTheme(): void {
  applyTheme(loadTheme());
  if (loadTheme() === "system") {
    window.matchMedia("(prefers-color-scheme: light)")
      .addEventListener("change", () => applyTheme("system"));
  }
}
