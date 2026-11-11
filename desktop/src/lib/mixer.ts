/**
 * Pure mixer logic shared by the preview player and the render request. The
 * formula matches the engine's `mixer.mix_gains`, per channel: with `keep`,
 * the output is mix + Σ (gain · balance − 1) · stem (the residual stays at
 * unity); with `drop`, it is Σ gain · balance · stem. Balance comes from the
 * stem's pan (see `panGains`).
 */

export type Residual = "keep" | "drop";

export interface StemControl {
  /** Fader position in dB (MIN_DB means silent). */
  db: number;
  muted: boolean;
  soloed: boolean;
  /** Stereo balance from −1 (left) to 1 (right). */
  pan: number;
}

/** Left/right gain pair of one track. */
export type Stereo = [number, number];

export const MIN_DB = -30;
export const MAX_DB = 6;

/** Decoded audio above this is reduced to a lower sample rate (ADR-007). */
export const MEMORY_BUDGET_MB = 700;
export const REDUCED_RATE = 22_050;

export function dbToGain(db: number): number {
  return db <= MIN_DB ? 0 : 10 ** (db / 20);
}

export function formatDb(db: number): string {
  if (db <= MIN_DB) return "−∞ dB";
  const rounded = Math.round(db * 10) / 10;
  return `${rounded > 0 ? "+" : rounded < 0 ? "−" : ""}${Math.abs(rounded).toFixed(1)} dB`;
}

/** Linear gain per stem after mute, solo and fader (any solo silences the rest). */
export function effectiveGains(
  controls: Record<string, StemControl>,
): Record<string, number> {
  const anySolo = Object.values(controls).some((c) => c.soloed);
  const gains: Record<string, number> = {};
  for (const [stem, control] of Object.entries(controls)) {
    const audible = anySolo ? control.soloed : !control.muted;
    gains[stem] = audible ? dbToGain(control.db) : 0;
  }
  return gains;
}

/** Track settings of a stem in a DAW session (see the engine's `daw.export`). */
export interface SessionTrack {
  /** Linear fader gain (0 at the bottom of the fader). */
  gain: number;
  pan: number;
  /** Muted in the DAW: muted here, or silenced by another stem's solo. */
  muted: boolean;
}

/**
 * Mixer state as DAW tracks: the fader and pan go in as they are, and mute
 * and solo become a mute flag, so the session sounds like the preview.
 */
export function sessionTracks(
  controls: Record<string, StemControl>,
): Record<string, SessionTrack> {
  const anySolo = Object.values(controls).some((c) => c.soloed);
  return Object.fromEntries(
    Object.entries(controls).map(([stem, control]) => [
      stem,
      {
        gain: dbToGain(control.db),
        pan: control.pan,
        muted: anySolo ? !control.soloed : control.muted,
      },
    ]),
  );
}

/**
 * Balance law for a stereo stem (same as the engine's `pan_gains`): the
 * centre leaves both channels at unity; turning towards one side fades the
 * other channel linearly down to silence.
 */
export function panGains(pan: number): Stereo {
  const p = Math.max(-1, Math.min(1, pan));
  return [p > 0 ? 1 - p : 1, p < 0 ? 1 + p : 1];
}

/** Pan per stem from the controls (missing stems stay centred). */
export function pans(
  controls: Record<string, StemControl>,
): Record<string, number> {
  return Object.fromEntries(
    Object.entries(controls).map(([stem, control]) => [stem, control.pan]),
  );
}

/**
 * Gain-node values for the player: the decoded mix plus one left/right pair
 * per stem. `original` (A/B) plays the untouched mix.
 */
export function nodeGains(
  gains: Record<string, number>,
  residual: Residual,
  original: boolean,
  pan: Record<string, number> = {},
): { mix: number; stems: Record<string, Stereo> } {
  const stems: Record<string, Stereo> = {};
  for (const [stem, gain] of Object.entries(gains)) {
    const [left, right] = panGains(pan[stem] ?? 0);
    const offset = residual === "keep" ? 1 : 0;
    stems[stem] = original
      ? [0, 0]
      : [gain * left - offset, gain * right - offset];
  }
  return { mix: original || residual === "keep" ? 1 : 0, stems };
}

/** Stems the player needs decoded to sound right with these settings. */
export function stemsNeeded(
  gains: Record<string, number>,
  residual: Residual,
  pan: Record<string, number> = {},
): string[] {
  return Object.entries(gains)
    .filter(
      ([stem, gain]) =>
        residual === "drop" ||
        Math.abs(gain - 1) > 1e-6 ||
        Math.abs(pan[stem] ?? 0) > 1e-6,
    )
    .map(([stem]) => stem);
}

/** Pan readout: "C", "L40" or "R100". */
export function formatPan(pan: number): string {
  const value = Math.round(Math.abs(pan) * 100);
  if (value === 0) return "C";
  return `${pan < 0 ? "L" : "R"}${value}`;
}

/** Decoded size in MB of `seconds` of stereo float32 audio per track. */
export function decodedMb(
  seconds: number,
  tracks: number,
  rate: number,
): number {
  return (seconds * rate * 2 * 4 * tracks) / 2 ** 20;
}

/** Length in seconds of a canonical engine WAV (44.1 kHz stereo float32). */
export function wavSeconds(bytes: number): number {
  return Math.max(0, bytes - 44) / (44_100 * 2 * 4);
}

export function formatTime(seconds: number): string {
  const safe = Math.max(0, seconds);
  const minutes = Math.floor(safe / 60);
  const rest = Math.floor(safe % 60);
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

/** LCD clock: minutes, seconds and tenths ("03:07.4"). */
export function formatClock(seconds: number): string {
  const tenths = Math.floor(Math.max(0, seconds) * 10);
  const minutes = Math.floor(tenths / 600);
  const rest = (tenths % 600) / 10;
  return `${String(minutes).padStart(2, "0")}:${rest.toFixed(1).padStart(4, "0")}`;
}

/** Playback position for a loop region, wrapping once past its end. */
export function wrapPosition(
  position: number,
  loop: { start: number; end: number } | null,
): number {
  if (!loop || loop.end - loop.start <= 0 || position < loop.end)
    return position;
  const span = loop.end - loop.start;
  return loop.start + ((position - loop.start) % span);
}

/** SVG path of a [min, max] peak list drawn into a `width`×`height` box. */
export function peaksPath(
  peaks: number[][],
  width: number,
  height: number,
): string {
  if (peaks.length === 0) return "";
  const mid = height / 2;
  const step = width / peaks.length;
  const top: string[] = [];
  const bottom: string[] = [];
  peaks.forEach(([min, max], i) => {
    const x = (i * step).toFixed(1);
    top.push(`${x} ${(mid - Math.max(max, 0.004) * mid).toFixed(1)}`);
    bottom.push(`${x} ${(mid - Math.min(min, -0.004) * mid).toFixed(1)}`);
  });
  return `M${top.join("L")}L${bottom.reverse().join("L")}Z`;
}
