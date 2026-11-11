/**
 * Translation checks, run in CI with the other unit tests (`pnpm test`).
 * `pnpm check` already fails on a missing or unknown key; these tests add
 * readable messages and the rules TypeScript cannot see.
 */
import { describe, expect, it } from "vitest";
import {
  LOCALES,
  MAINTAINED,
  detectLocale,
  dictionaries,
  isLocale,
  translate,
  type Locale,
} from "./i18n.svelte";
import { en } from "./i18n/en";

const codes = Object.keys(LOCALES) as Locale[];
const sourceKeys = Object.keys(en).sort();
const placeholders = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort();

describe.each(codes.filter((code) => code !== "en"))("locale %s", (code) => {
  const dictionary = dictionaries[code];

  it("has every key of the English source, and no other", () => {
    const keys = Object.keys(dictionary);
    expect(
      sourceKeys.filter((key) => !keys.includes(key)),
      "missing keys",
    ).toEqual([]);
    expect(
      keys.filter((key) => !sourceKeys.includes(key)),
      "keys not in en.ts",
    ).toEqual([]);
  });

  it("translates every string", () => {
    const empty = Object.entries(dictionary)
      .filter(([, text]) => !text.trim())
      .map(([key]) => key);
    expect(empty, "empty strings").toEqual([]);
  });

  it("keeps the {placeholders} of the English source", () => {
    for (const [key, text] of Object.entries(en)) {
      expect(
        placeholders(dictionary[key as keyof typeof en]),
        `${code} ${key}`,
      ).toEqual(placeholders(text));
    }
  });
});

describe("i18n", () => {
  it("has a dictionary for every listed language", () => {
    expect(Object.keys(dictionaries).sort()).toEqual([...codes].sort());
    expect(MAINTAINED.every(isLocale)).toBe(true);
  });

  it("uses non-breaking spaces before French double punctuation", () => {
    const loose = Object.entries(dictionaries.fr)
      .filter(([, text]) => / [:;?!]/.test(text))
      .map(([key]) => key);
    expect(loose, "use U+00A0 before : ; ? !").toEqual([]);
  });

  it("detects the language from the system preferences", () => {
    expect(detectLocale("es-ES")).toBe("es");
    expect(detectLocale("es-419")).toBe("es");
    expect(detectLocale("pt-BR")).toBe("pt-BR");
    expect(detectLocale("pt-PT")).toBe("pt-BR");
    expect(detectLocale("fr-CA")).toBe("fr");
    expect(detectLocale("de-AT")).toBe("de");
    expect(detectLocale("it_IT")).toBe("it");
    expect(detectLocale("ja-JP")).toBe("en");
    expect(detectLocale(["ca-ES", "es-ES", "en-US"])).toBe("es");
    expect(detectLocale([])).toBe("en");
    expect(detectLocale(undefined)).toBe("en");
  });

  it("recognises supported locale codes only", () => {
    expect(isLocale("pt-BR")).toBe(true);
    expect(isLocale("pt")).toBe(false);
    expect(isLocale(null)).toBe(false);
  });

  it("translates a key in each language", () => {
    expect(translate("en", "stem.guitar")).toBe("Guitar");
    expect(translate("es", "stem.guitar")).toBe("Guitarra");
    expect(translate("pt-BR", "stem.guitar")).toBe("Guitarra");
    expect(translate("fr", "stem.guitar")).toBe("Guitare");
    expect(translate("de", "stem.guitar")).toBe("Gitarre");
    expect(translate("it", "stem.guitar")).toBe("Chitarra");
  });
});
