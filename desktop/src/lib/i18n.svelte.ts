/**
 * Interface languages and the reactive locale.
 *
 * The strings live in `i18n/`, one file per locale, each typed against the
 * English source (`i18n/en.ts`), so a missing key fails `pnpm check`. See
 * docs/TRANSLATING.md to update a translation or add a language.
 */
import { de } from "./i18n/de";
import { en, type Dictionary, type MessageKey } from "./i18n/en";
import { es } from "./i18n/es";
import { fr } from "./i18n/fr";
import { it } from "./i18n/it";
import { ptBR } from "./i18n/pt-BR";

export type { Dictionary, MessageKey };

/**
 * The interface languages, each under its own name, in the order of the
 * Settings picker. Codes are BCP 47 tags, also used to format dates.
 */
export const LOCALES = {
  en: "English",
  es: "Español",
  "pt-BR": "Português (Brasil)",
  fr: "Français",
  de: "Deutsch",
  it: "Italiano",
} as const;
export type Locale = keyof typeof LOCALES;

/** Languages kept up to date by the maintainers; the rest by the community. */
export const MAINTAINED: readonly Locale[] = ["en", "es"];

export const dictionaries: Record<Locale, Dictionary> = {
  en,
  es,
  "pt-BR": ptBR,
  fr,
  de,
  it,
};

const CODES = Object.keys(LOCALES) as Locale[];

export function isLocale(value: unknown): value is Locale {
  return typeof value === "string" && CODES.includes(value as Locale);
}

/**
 * The best interface language for the user's preferred languages (BCP 47
 * tags, most preferred first): an exact match, then the same language in
 * another region (`fr-CA` → `fr`, `pt-PT` → `pt-BR`). English otherwise.
 */
export function detectLocale(
  languages: string | readonly string[] | undefined,
): Locale {
  const tags = typeof languages === "string" ? [languages] : (languages ?? []);
  for (const tag of tags) {
    const wanted = tag.toLowerCase().replace("_", "-");
    const exact = CODES.find((code) => code.toLowerCase() === wanted);
    if (exact) return exact;
    const language = wanted.split("-")[0];
    const sameLanguage = CODES.find(
      (code) => code.toLowerCase().split("-")[0] === language,
    );
    if (sameLanguage) return sameLanguage;
  }
  return "en";
}

function systemLanguages(): readonly string[] | undefined {
  if (typeof navigator === "undefined") return undefined;
  return navigator.languages?.length
    ? navigator.languages
    : [navigator.language];
}

export const i18n = $state<{ locale: Locale }>({
  locale: detectLocale(systemLanguages()),
});

/** Tell the browser (screen readers, hyphenation) which language is shown. */
export function applyLocale(locale: Locale): void {
  if (typeof document !== "undefined") document.documentElement.lang = locale;
}

export function t(key: MessageKey): string {
  return dictionaries[i18n.locale][key] || en[key];
}

export function translate(locale: Locale, key: MessageKey): string {
  return dictionaries[locale][key];
}
