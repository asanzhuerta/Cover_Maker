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

/** Human-readable label for a stem id. */
export function stemLabel(stem: Stem): string {
  return stem.charAt(0).toUpperCase() + stem.slice(1);
}
