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

/** Signature colour per stem, used for chips, icons and waveforms. */
export const STEM_COLORS: Record<Stem, string> = {
  vocals: "#ff5c8a",
  guitar: "#ffb238",
  drums: "#3fd0ff",
  bass: "#9b7bff",
  piano: "#4fe08f",
  other: "#a7b1c8",
};

/** Colour for a stem id from the API (unknown ids fall back to "other"). */
export function stemColor(stem: string): string {
  return STEM_COLORS[stem as Stem] ?? STEM_COLORS.other;
}

/** Human-readable label for a stem id. */
export function stemLabel(stem: Stem): string {
  return stem.charAt(0).toUpperCase() + stem.slice(1);
}
