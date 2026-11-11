import { describe, expect, it } from "vitest";
import { about, contactLinks, localized } from "./about";
import { LOCALES, type Locale } from "./i18n.svelte";

describe("about", () => {
  it("has every user-facing text in every interface language", () => {
    const texts = [
      about.author.bio,
      about.app.description,
      ...about.credits.map((credit) => credit.role),
    ];
    for (const text of texts) {
      for (const locale of Object.keys(LOCALES) as Locale[]) {
        expect(text[locale], `${locale}: ${text.en}`).toBeTruthy();
      }
    }
  });

  it("credits the main open-source components with https links", () => {
    const names = about.credits.map((credit) => credit.name);
    for (const name of [
      "Tauri",
      "Svelte",
      "PyTorch",
      "audio-separator",
      "yt-dlp",
      "FastAPI",
    ]) {
      expect(names).toContain(name);
    }
    for (const credit of about.credits) {
      expect(credit.url).toMatch(/^https:\/\//);
    }
    expect(about.notices).toMatch(/THIRD_PARTY_NOTICES\.md$/);
  });

  it("builds contact links and skips empty fields", () => {
    const links = contactLinks({
      ...about.author,
      github: "https://github.com/someone",
      email: "a@example.com",
      website: "",
    });
    expect(links).toEqual([
      {
        kind: "github",
        href: "https://github.com/someone",
        label: "github.com/someone",
      },
      { kind: "email", href: "mailto:a@example.com", label: "a@example.com" },
    ]);
  });

  it("falls back to English", () => {
    expect(localized({ en: "Hi", es: "" }, "es")).toBe("Hi");
  });
});
