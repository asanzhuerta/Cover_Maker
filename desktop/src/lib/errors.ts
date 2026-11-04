/**
 * Turns engine error texts into a short, translated hint about what to do.
 * The engine's own message stays visible; the hint adds the next step.
 */
import type { MessageKey } from "./i18n.svelte";

const HINTS: [RegExp, MessageKey][] = [
  [/without ffmpeg|needs ffmpeg/i, "hint.ffmpeg"],
  [/could not decode|could not encode/i, "hint.decode"],
  [/out of memory|\boom\b/i, "hint.memory"],
  [/separation worker exited/i, "hint.worker"],
  [/separation support is not installed/i, "hint.runtime"],
  [/not installed|install the model/i, "hint.model"],
  [
    /could not download|no audio file was found|could not read (playlist|\w{11})/i,
    "hint.download",
  ],
  [/missing from the library/i, "hint.cache"],
  [/file not found|no longer exists/i, "hint.missingFile"],
  [/could not reach the catalogue/i, "hint.network"],
];

export function errorHint(
  message: string | null | undefined,
): MessageKey | null {
  if (!message) return null;
  for (const [pattern, key] of HINTS) if (pattern.test(message)) return key;
  return null;
}
