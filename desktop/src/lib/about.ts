/**
 * Content of the About page. Edit `about.json` (next to this file) to change
 * the author profile, the app description or the credits; texts that the
 * user reads come in English and Spanish.
 */
import data from "./about.json";
import type { Locale } from "./i18n.svelte";

export type Localized = Record<Locale, string>;

export interface Credit {
  name: string;
  url: string;
  licence: string;
  role: Localized;
}

export interface About {
  author: {
    name: string;
    photo: string;
    email: string;
    website: string;
    github: string;
    bio: Localized;
  };
  app: { repository: string; description: Localized };
  credits: Credit[];
  notices: string;
}

export const about: About = data;

export function localized(text: Localized, locale: Locale): string {
  return text[locale] || text.en;
}

/** Contact links shown under the profile, skipping empty fields. */
export function contactLinks(
  author: About["author"],
): { kind: "github" | "email" | "website"; href: string; label: string }[] {
  const links: {
    kind: "github" | "email" | "website";
    href: string;
    label: string;
  }[] = [];
  if (author.github) {
    links.push({
      kind: "github",
      href: author.github,
      label: author.github.replace(/^https?:\/\//, ""),
    });
  }
  if (author.email) {
    links.push({
      kind: "email",
      href: `mailto:${author.email}`,
      label: author.email,
    });
  }
  if (author.website) {
    links.push({
      kind: "website",
      href: author.website,
      label: author.website.replace(/^https?:\/\//, ""),
    });
  }
  return links;
}
