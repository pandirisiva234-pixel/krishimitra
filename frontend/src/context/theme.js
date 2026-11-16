// Light / dark / system theme. The choice is stored in this browser (localStorage) when possible.
const KEY = "krishimitra_theme";
export const THEMES = ["light", "dark", "system"];

export function savedTheme() {
  try {
    const value = localStorage.getItem(KEY);
    return THEMES.includes(value) ? value : "system";
  } catch {
    return "system";
  }
}

export function resolveTheme(choice) {
  if (choice !== "system") return choice;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(choice) {
  document.documentElement.dataset.theme = resolveTheme(choice);
  try {
    localStorage.setItem(KEY, choice);
  } catch {
    /* storage unavailable: the theme still applies for this visit */
  }
}
