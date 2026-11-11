/** Top-level stems: together they make the whole song. */
export const STEMS = [
  "vocals",
  "guitar",
  "drums",
  "bass",
  "piano",
  "other",
] as const;

/**
 * Sub-stems split a top-level stem further (id `<parent>.<part>`); together
 * they make their parent. The engine runs an extra model on the parent stem.
 */
export const SUB_STEMS = {
  vocals: ["vocals.lead", "vocals.backing"],
} as const;

export type TopStem = (typeof STEMS)[number];
export type SubStem = (typeof SUB_STEMS)[keyof typeof SUB_STEMS][number];
export type Stem = TopStem | SubStem;

/** Every stem a user can choose, each sub-stem right after its parent. */
export const CHOOSABLE: readonly Stem[] = STEMS.flatMap((stem) => [
  stem,
  ...((SUB_STEMS as Partial<Record<TopStem, readonly SubStem[]>>)[stem] ?? []),
]);

/**
 * Signature colour per stem, used for chips, icons, meters and waveforms.
 * For text in the light theme, mix with the text colour (`.stem-ink`).
 * Lead vocals keep the vocals' gold, lighter; backing vocals are dusty rose.
 */
export const STEM_COLORS: Record<Stem, string> = {
  vocals: "#ffcf5c",
  "vocals.lead": "#ffe9a8",
  "vocals.backing": "#e79aa6",
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

/** Human-readable label for a top-level stem id. */
export function stemLabel(stem: TopStem): string {
  return stem.charAt(0).toUpperCase() + stem.slice(1);
}

/** True for a stem id the UI knows (top-level or sub-stem). */
export function isStem(stem: string): stem is Stem {
  return stem in STEM_COLORS;
}

/**
 * Mixer lanes for the stems a song has, in the usual order. When every
 * sub-stem of a stem is there, the sub-stems take its place, so that no audio
 * is played twice (the engine's `finest`).
 */
export function mixerStems(available: Iterable<string>): Stem[] {
  const have = new Set(available);
  const lanes: Stem[] = [];
  for (const stem of STEMS) {
    const parts: readonly SubStem[] =
      (SUB_STEMS as Partial<Record<TopStem, readonly SubStem[]>>)[stem] ?? [];
    if (parts.length && parts.every((part) => have.has(part))) {
      lanes.push(...parts);
    } else if (have.has(stem)) {
      lanes.push(stem);
    }
  }
  return lanes;
}
