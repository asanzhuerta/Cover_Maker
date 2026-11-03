/** User preferences persisted in localStorage (per machine, not shared). */
import { i18n, type Locale } from "./i18n.svelte";

export type Theme = "system" | "light" | "dark";
export type Format = "wav" | "flac" | "mp3";

export interface Settings {
  locale: Locale;
  theme: Theme;
  outputDir: string;
  format: Format;
  allowCpu: boolean;
  welcomed: boolean;
}

const KEY = "cover_maker.settings";

const defaults: Settings = {
  locale: i18n.locale,
  theme: "dark",
  outputDir: "",
  format: "wav",
  allowCpu: false,
  welcomed: false,
};

function load(): Settings {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...defaults, ...JSON.parse(raw) } : { ...defaults };
  } catch {
    return { ...defaults };
  }
}

export const settings = $state<Settings>(load());

export function saveSettings(): void {
  i18n.locale = settings.locale;
  applyTheme(settings.theme);
  try {
    localStorage.setItem(KEY, JSON.stringify(settings));
  } catch {
    // Storage can be unavailable (private mode); settings then last for the session.
  }
}

export function applyTheme(theme: Theme): void {
  if (typeof document === "undefined") return;
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
}
