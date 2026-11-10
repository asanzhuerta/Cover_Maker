/**
 * Keyboard shortcuts of the player and the mixer. `shortcutFor` maps a key
 * press to an action; it returns null while the user types in a field, so
 * the keys keep their normal meaning there.
 */

export type Shortcut =
  | { action: "play" }
  | { action: "mute" }
  | { action: "solo" }
  | { action: "lane"; index: number }
  | { action: "laneBy"; step: number }
  | { action: "loop" }
  | { action: "ab" }
  | { action: "seek"; seconds: number }
  | { action: "help" };

export interface KeyPress {
  key: string;
  code?: string;
  ctrlKey?: boolean;
  metaKey?: boolean;
  altKey?: boolean;
  shiftKey?: boolean;
  target: EventTarget | null;
}

/** Input types that take key presses as text (not buttons or toggles). */
const TEXT_TYPES = new Set([
  "text",
  "search",
  "url",
  "email",
  "number",
  "password",
  "tel",
  "date",
  "time",
]);

interface ElementLike {
  tagName?: string;
  type?: string;
  isContentEditable?: boolean;
  getAttribute?: (name: string) => string | null;
}

/** True while focus is in a place that takes the key itself. */
export function typingIn(target: EventTarget | null, key: string): boolean {
  const element = target as ElementLike | null;
  if (!element?.tagName) return false;
  const tag = element.tagName.toLowerCase();
  if (element.isContentEditable || tag === "textarea" || tag === "select")
    return true;
  if (tag === "input" && TEXT_TYPES.has((element.type ?? "").toLowerCase()))
    return true;
  // Sliders use the arrow keys, buttons and toggles use Space.
  const isSlider =
    (tag === "input" && element.type === "range") ||
    element.getAttribute?.("role") === "slider";
  if (isSlider && key.startsWith("Arrow")) return true;
  const isControl =
    tag === "button" ||
    (tag === "input" && ["checkbox", "radio"].includes(element.type ?? "")) ||
    tag === "a";
  return isControl && key === " ";
}

export const SEEK_SECONDS = 5;

export function shortcutFor(press: KeyPress): Shortcut | null {
  if (press.ctrlKey || press.metaKey || press.altKey) return null;
  if (typingIn(press.target, press.key)) return null;
  const key = press.key;
  if (key === " ") return { action: "play" };
  if (key === "?") return { action: "help" };
  if (key === "ArrowLeft") return { action: "seek", seconds: -SEEK_SECONDS };
  if (key === "ArrowRight") return { action: "seek", seconds: SEEK_SECONDS };
  if (key === "ArrowUp") return { action: "laneBy", step: -1 };
  if (key === "ArrowDown") return { action: "laneBy", step: 1 };
  if (/^[1-6]$/.test(key)) return { action: "lane", index: Number(key) - 1 };
  switch (key.toLowerCase()) {
    case "m":
      return { action: "mute" };
    case "s":
      return { action: "solo" };
    case "l":
      return { action: "loop" };
    case "a":
      return { action: "ab" };
  }
  return null;
}

/** Rows of the shortcut help, in display order. */
export const SHORTCUT_HELP = [
  { keys: ["Space"], label: "shortcuts.play" },
  { keys: ["1", "–", "6"], label: "shortcuts.select" },
  { keys: ["↑", "↓"], label: "shortcuts.lane" },
  { keys: ["M"], label: "shortcuts.mute" },
  { keys: ["S"], label: "shortcuts.solo" },
  { keys: ["L"], label: "shortcuts.loop" },
  { keys: ["A"], label: "shortcuts.ab" },
  { keys: ["←", "→"], label: "shortcuts.seek" },
  { keys: ["?"], label: "shortcuts.help" },
] as const;
