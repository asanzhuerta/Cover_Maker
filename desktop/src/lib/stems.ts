/** Stems a user can choose to extract or remove. */
export const STEMS = [
  "vocals",
  "guitar",
  "drums",
  "bass",
  "piano",
  "other",
] as const;

export type Stem = (typeof STEMS)[number];

/**
 * Signature colour per stem, used for chips, icons, meters and waveforms.
 * For text in the light theme, mix with the text colour (`.stem-ink`).
 */
export const STEM_COLORS: Record<Stem, string> = {
  vocals: "#ffcf5c",
  guitar: "#ff8f4d",
  drums: "#5fd3b5",
  bass: "#6fa8dc",
  piano: "#c8d46a",
  other: "#9b948a",
};

/** Colour for a stem id from the API (unknown ids fall back to "other"). */
export function stemColor(stem: string): string {
  return STEM_COLORS[stem as Stem] ?? STEM_COLORS.other;
}

/** Human-readable label for a stem id. */
export function stemLabel(stem: Stem): string {
  return stem.charAt(0).toUpperCase() + stem.slice(1);
}
