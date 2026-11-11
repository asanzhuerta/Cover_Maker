/** User preferences persisted in localStorage (per machine, not shared). */
import { applyLocale, i18n, isLocale, type Locale } from "./i18n.svelte";

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

function stored(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function load(raw: string | null): Settings {
  try {
    const loaded: Settings = raw
      ? { ...defaults, ...JSON.parse(raw) }
      : { ...defaults };
    // A language removed or renamed since it was saved falls back to the default.
    if (!isLocale(loaded.locale)) loaded.locale = defaults.locale;
    return loaded;
  } catch {
    return { ...defaults };
  }
}

const initial = stored();

/** True on the very first start: nothing has been saved yet. */
export const firstStart = initial === null;

export const settings = $state<Settings>(load(initial));

/**
 * On the first start of an installed app, use the language picked in the
 * installer as the default; Settings can change it later.
 */
export async function applyInstallerLocale(): Promise<void> {
  if (!firstStart) return;
  try {
    const { invoke } = await import("@tauri-apps/api/core");
    const locale = await invoke<string | null>("installer_locale");
    if (isLocale(locale)) {
      settings.locale = locale;
      saveSettings();
    }
  } catch {
    // Not installed with the NSIS installer (development): keep the default.
  }
}

export function saveSettings(): void {
  i18n.locale = settings.locale;
  applyLocale(settings.locale);
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
