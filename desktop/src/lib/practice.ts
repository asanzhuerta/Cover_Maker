/**
 * Practice tools (M14): pitch and tempo maths, bar-snapped loops, section
 * markers, the click stem and the speed trainer. Pure functions only; the
 * transport wires them to the player (ADR-010).
 */

import type { Region } from "./transport.svelte";

export const MIN_TEMPO = 0.5;
export const MAX_TEMPO = 1.5;
export const MAX_SEMITONES = 12;
export const MAX_CENTS = 50;
export const BEATS_PER_BAR = 4;

// Same click recipe as the engine (engine/src/cover_maker/audio/practice.py).
export const CLICK_HZ = 1000;
export const ACCENT_HZ = 1500;
export const CLICK_SECONDS = 0.03;
export const CLICK_DECAY = 150;
export const CLICK_LEVEL = 0.5;
export const ACCENT_LEVEL = 0.8;

export interface Marker {
  name: string;
  time: number;
}

export interface Trainer {
  on: boolean;
  /** Tempo factor the trainer starts from. */
  start: number;
  /** Tempo added after every `every` passes (factor, e.g. 0.05 = 5 %). */
  step: number;
  every: number;
  /** Tempo factor the trainer stops at. */
  target: number;
}

export const freshTrainer = (): Trainer => ({
  on: false,
  start: 0.7,
  step: 0.05,
  every: 2,
  target: 1,
});

/**
 * Semitones the master-bus stretch applies. Sources play `tempo` times
 * faster (a resample, which raises the pitch by 12·log2(tempo)), so the
 * stretch takes that back and adds the user's shift.
 */
export function pitchCorrection(
  tempo: number,
  semitones: number,
  cents: number,
): number {
  return semitones + cents / 100 - 12 * Math.log2(tempo);
}

export const clampTempo = (tempo: number) =>
  Math.min(MAX_TEMPO, Math.max(MIN_TEMPO, tempo));

const NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"];

/** The key after shifting by whole semitones, e.g. ("E", "minor", -1) → "Ebm". */
export function shiftedKey(
  tonic: string,
  mode: string,
  semitones: number,
): string {
  const index = NAMES.indexOf(tonic);
  if (index < 0) return tonic;
  const shifted = NAMES[(((index + Math.round(semitones)) % 12) + 12) % 12];
  return mode === "minor" ? `${shifted}m` : shifted;
}

/** Tuning offset in cents folded into [-50, 50). */
export function foldCents(cents: number): number {
  return ((((cents + 50) % 100) + 100) % 100) - 50;
}

export function formatCents(cents: number): string {
  const value = Math.round(cents);
  return value === 0 ? "±0" : `${value > 0 ? "+" : "−"}${Math.abs(value)}`;
}

export function formatShift(semitones: number, cents: number): string {
  const parts: string[] = [];
  if (semitones)
    parts.push(`${semitones > 0 ? "+" : "−"}${Math.abs(semitones)} st`);
  if (cents) parts.push(`${formatCents(cents)} ¢`);
  return parts.join(" ") || "0 st";
}

export const formatTempo = (tempo: number) => `${Math.round(tempo * 100)} %`;

/** Nearest downbeat to `time` (or `time` when there is no grid). */
export function snapToBar(time: number, downbeats: number[]): number {
  if (downbeats.length === 0) return time;
  let best = downbeats[0];
  for (const bar of downbeats)
    if (Math.abs(bar - time) < Math.abs(best - time)) best = bar;
  return best;
}

/** A loop region with both ends on bar lines, at least one bar long. */
export function snapRegion(
  region: Region,
  downbeats: number[],
  duration: number,
): Region {
  if (downbeats.length === 0) return region;
  const start = snapToBar(region.start, downbeats);
  let end = snapToBar(region.end, downbeats);
  if (end <= start) {
    const next = downbeats.find((bar) => bar > start);
    end = next ?? duration;
  }
  // The last bar runs to the end of the song.
  if (end === downbeats[downbeats.length - 1] && region.end > end)
    end = duration;
  return { start, end: Math.min(end, duration) };
}

/** 1-based bar number at `time` (0 before the first downbeat). */
export function barAt(time: number, downbeats: number[]): number {
  let bar = 0;
  for (const start of downbeats) {
    if (start > time + 1e-6) break;
    bar += 1;
  }
  return bar;
}

export function sortMarkers(markers: Marker[]): Marker[] {
  return [...markers].sort((a, b) => a.time - b.time);
}

/** From a marker to the next one (or the end of the song). */
export function sectionRegion(
  markers: Marker[],
  index: number,
  duration: number,
): Region | null {
  const sorted = sortMarkers(markers);
  const marker = sorted[index];
  if (!marker) return null;
  return { start: marker.time, end: sorted[index + 1]?.time ?? duration };
}

/** Name for a new marker: the next free "Section N". */
export function nextMarkerName(markers: Marker[], base: string): string {
  let n = markers.length + 1;
  const names = new Set(markers.map((m) => m.name));
  while (names.has(`${base} ${n}`)) n += 1;
  return `${base} ${n}`;
}

/** Seconds of one bar of count-in at the played tempo. */
export function countInSeconds(
  bpm: number,
  tempo: number,
  beats = BEATS_PER_BAR,
): number {
  if (bpm <= 0) return 0;
  return (beats * 60) / (bpm * tempo);
}

/** Tempo after `passes` loop passes. */
export function trainerTempo(trainer: Trainer, passes: number): number {
  const steps = Math.floor(passes / Math.max(1, trainer.every));
  const direction = trainer.target >= trainer.start ? 1 : -1;
  const raw = trainer.start + direction * Math.abs(trainer.step) * steps;
  const bounded =
    direction > 0
      ? Math.min(raw, trainer.target)
      : Math.max(raw, trainer.target);
  return clampTempo(Math.round(bounded * 1000) / 1000);
}

export function trainerDone(trainer: Trainer, passes: number): boolean {
  return Math.abs(trainerTempo(trainer, passes) - trainer.target) < 1e-6;
}

/** True when playback jumped back from the end of the loop to its start. */
export function loopWrapped(
  previous: number,
  next: number,
  loop: Region | null,
): boolean {
  if (!loop) return false;
  const length = loop.end - loop.start;
  return next < previous && previous - next > length / 2;
}

/** Click track samples on the beat grid (seconds), accented on downbeats. */
export function renderClick(
  sampleRate: number,
  frames: number,
  beats: number[],
  downbeats: number[],
): Float32Array {
  const out = new Float32Array(frames);
  const length = Math.floor(CLICK_SECONDS * sampleRate);
  const accented = new Set(downbeats.map((d) => Math.round(d * 1000)));
  for (const beat of beats) {
    const start = Math.round(beat * sampleRate);
    if (start < 0 || start >= frames) continue;
    const accent = accented.has(Math.round(beat * 1000));
    const freq = accent ? ACCENT_HZ : CLICK_HZ;
    const level = accent ? ACCENT_LEVEL : CLICK_LEVEL;
    const end = Math.min(frames, start + length);
    for (let i = start; i < end; i++) {
      const t = (i - start) / sampleRate;
      out[i] +=
        Math.sin(2 * Math.PI * freq * t) * Math.exp(-t * CLICK_DECAY) * level;
    }
  }
  return out;
}
