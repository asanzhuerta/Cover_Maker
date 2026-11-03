/** Deterministic decorative waveform shapes (no audio is analysed). */

/**
 * Bar heights in (0, 1] for a waveform of `count` bars. The same seed always
 * gives the same shape, so a song keeps its look across reloads.
 */
export function waveBars(seed: string, count: number): number[] {
  let state = 2166136261;
  for (const char of seed) {
    state = Math.imul(state ^ char.charCodeAt(0), 16777619) >>> 0;
  }
  const bars: number[] = [];
  for (let i = 0; i < count; i++) {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    const noise = state / 4294967296;
    const envelope = 0.55 + 0.45 * Math.sin((i / count) * Math.PI);
    bars.push(Math.max(0.12, Math.min(1, envelope * (0.35 + 0.65 * noise))));
  }
  return bars;
}
