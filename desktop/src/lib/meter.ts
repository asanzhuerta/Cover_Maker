/**
 * Peak-programme meter ballistics for the mixer's LED meters. The reading
 * jumps up at once (attack), falls back at a fixed rate in dB (IEC 60268-10
 * type I: 20 dB in 1.7 s) and a peak marker holds the highest value for a
 * moment. The meters are drawn straight from this state, never eased in CSS.
 */

/** Bottom of the scale: anything quieter shows as off. */
export const METER_FLOOR_DB = -48;
/** Fall-back rate of the reading. */
export const RELEASE_DB_PER_S = 20 / 1.7;
/** How long the peak marker stays before it falls. */
export const PEAK_HOLD_S = 1.5;
/** Envelope resolution the meters read (points per second of audio). */
export const METER_POINTS_PER_S = 25;
/** Updates further apart than this are a jump, not playback. */
const MAX_GAP_S = 0.5;
/** Limit of the engine's peaks endpoint. */
export const MAX_POINTS = 10_000;

export interface MeterState {
  /** Current reading in dBFS. */
  db: number;
  /** Peak marker in dBFS. */
  peak: number;
  /** Seconds since the peak marker was set. */
  held: number;
}

export const silentMeter = (): MeterState => ({
  db: METER_FLOOR_DB,
  peak: METER_FLOOR_DB,
  held: 0,
});

export function toDb(linear: number): number {
  return linear > 0
    ? Math.max(METER_FLOOR_DB, 20 * Math.log10(linear))
    : METER_FLOOR_DB;
}

/** Advance a meter by `dt` seconds with a new input level in dBFS. */
export function meterStep(
  state: MeterState,
  inputDb: number,
  dt: number,
): MeterState {
  const input = Math.max(METER_FLOOR_DB, inputDb);
  const fallen = state.db - RELEASE_DB_PER_S * dt;
  const db = Math.max(input, fallen, METER_FLOOR_DB);
  if (db >= state.peak) return { db, peak: db, held: 0 };
  const held = state.held + dt;
  const peak =
    held > PEAK_HOLD_S
      ? Math.max(db, state.peak - RELEASE_DB_PER_S * dt)
      : state.peak;
  return { db, peak, held };
}

/** Position of a dBFS value on the meter scale (0 = floor, 1 = 0 dBFS). */
export function meterShare(db: number): number {
  return Math.min(1, Math.max(0, 1 - db / METER_FLOOR_DB));
}

/** Points to request for a meter envelope of `seconds` of audio. */
export function envelopePoints(seconds: number): number {
  return Math.max(
    50,
    Math.min(MAX_POINTS, Math.ceil(seconds * METER_POINTS_PER_S)),
  );
}

/**
 * Highest absolute sample of an envelope ([min, max] per point) between two
 * playback positions, so a short peak between two meter updates is not lost.
 */
export function envelopePeak(
  envelope: number[][],
  duration: number,
  from: number,
  to: number,
): number {
  if (envelope.length === 0 || duration <= 0) return 0;
  const index = (time: number) =>
    Math.min(
      envelope.length - 1,
      Math.max(0, Math.floor((time / duration) * envelope.length)),
    );
  const end = index(to);
  // A jump (seek, loop or a long pause between updates) reads only the current point.
  const start = to < from || to - from > MAX_GAP_S ? end : index(from);
  let peak = 0;
  for (let i = start; i <= end; i++) {
    const [min, max] = envelope[i];
    peak = Math.max(peak, Math.abs(min), Math.abs(max));
  }
  return peak;
}

/** Reduce an envelope to `points` [min, max] pairs for drawing a waveform. */
export function downsample(envelope: number[][], points: number): number[][] {
  if (envelope.length <= points) return envelope;
  const out: number[][] = [];
  const step = envelope.length / points;
  for (let i = 0; i < points; i++) {
    let min = 0;
    let max = 0;
    const end = Math.min(envelope.length, Math.round((i + 1) * step));
    for (let j = Math.round(i * step); j < end; j++) {
      min = Math.min(min, envelope[j][0]);
      max = Math.max(max, envelope[j][1]);
    }
    out.push([min, max]);
  }
  return out;
}
