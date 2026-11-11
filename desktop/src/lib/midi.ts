/** Audio-to-MIDI in the mixer (FR-MIDI-01): stem choice and progress. */

/** A `midi.progress` event: the stem being converted and how far it is. */
export interface MidiProgress {
  stem: string;
  index: number;
  total: number;
  fraction: number;
}

/** The progress in an engine event for this item, or null for any other event. */
export function midiProgress(
  event: { type: string; [key: string]: unknown },
  itemId: number,
): MidiProgress | null {
  if (event.type !== "midi.progress" || event.item !== itemId) return null;
  return {
    stem: String(event.stem ?? ""),
    index: Number(event.index ?? 0),
    total: Number(event.total ?? 0),
    fraction: Number(event.fraction ?? 0),
  };
}

/** Share of the whole request done, in [0, 1]: finished stems plus the current one. */
export function overallFraction(progress: MidiProgress): number {
  if (progress.total <= 0) return 0;
  const current = Math.min(1, Math.max(0, progress.fraction));
  return Math.min(1, Math.max(0, (progress.index + current) / progress.total));
}

/** Add or remove a stem, keeping the order of `all` (the mixer's lane order). */
export function toggleStem<T extends string>(
  chosen: readonly T[],
  stem: T,
  all: readonly T[],
): T[] {
  const next = new Set(chosen);
  if (next.has(stem)) next.delete(stem);
  else next.add(stem);
  return all.filter((s) => next.has(s));
}
