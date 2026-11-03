/**
 * Preview player (ADR-007): every track of a song plays from one AudioContext
 * and every source is started with the same `start(t)` time, which keeps them
 * sample-aligned. Gains change with short ramps to avoid clicks. Tracks are
 * decoded on demand; a track added while playing joins at the same position.
 */

import { wrapPosition } from "./mixer";

const RAMP_SECONDS = 0.015;

interface Track {
  buffer: AudioBuffer;
  gain: GainNode;
  source: AudioBufferSourceNode | null;
}

export class Player {
  readonly context: AudioContext;
  private tracks = new Map<string, Track>();
  private targets = new Map<string, number>();
  /** Context time at which `offset` was playing (only while playing). */
  private startedAt = 0;
  private offset = 0;
  private loop: { start: number; end: number } | null = null;
  private wanted = false;
  playing = false;
  duration = 0;

  constructor(sampleRate?: number) {
    this.context = new AudioContext(sampleRate ? { sampleRate } : undefined);
  }

  has(id: string): boolean {
    return this.tracks.has(id);
  }

  /** Decode a track (encoded file bytes) and connect it, silent until set. */
  async add(id: string, bytes: ArrayBuffer): Promise<void> {
    if (this.tracks.has(id)) return;
    const buffer = await this.context.decodeAudioData(bytes);
    const gain = this.context.createGain();
    gain.gain.value = this.targets.get(id) ?? 0;
    gain.connect(this.context.destination);
    const track: Track = { buffer, gain, source: null };
    this.tracks.set(id, track);
    this.duration = Math.max(this.duration, buffer.duration);
    if (this.playing) {
      const at = this.context.currentTime + 0.05;
      this.startSource(track, at, this.positionAt(at));
    }
  }

  setGain(id: string, value: number): void {
    this.targets.set(id, value);
    const track = this.tracks.get(id);
    if (!track) return;
    const now = this.context.currentTime;
    track.gain.gain.cancelScheduledValues(now);
    track.gain.gain.setTargetAtTime(value, now, RAMP_SECONDS / 3);
  }

  get position(): number {
    return this.playing
      ? this.positionAt(this.context.currentTime)
      : this.offset;
  }

  private positionAt(time: number): number {
    const raw = this.offset + (time - this.startedAt);
    return Math.max(0, Math.min(wrapPosition(raw, this.loop), this.duration));
  }

  private startSource(track: Track, at: number, position: number): void {
    const source = this.context.createBufferSource();
    source.buffer = track.buffer;
    if (this.loop) {
      source.loop = true;
      source.loopStart = this.loop.start;
      source.loopEnd = this.loop.end;
    }
    source.connect(track.gain);
    source.start(at, Math.min(position, track.buffer.duration));
    track.source = source;
  }

  async play(): Promise<void> {
    if (this.playing || this.tracks.size === 0) return;
    this.wanted = true;
    await this.context.resume();
    // A pause or a second play() may have happened while resuming.
    if (!this.wanted || this.playing) return;
    if (this.offset >= this.duration - 0.01)
      this.offset = this.loop?.start ?? 0;
    if (this.loop && this.offset >= this.loop.end)
      this.offset = this.loop.start;
    // One start time for every source = sample-aligned playback.
    const at = this.context.currentTime + 0.05;
    for (const track of this.tracks.values())
      this.startSource(track, at, this.offset);
    this.startedAt = at;
    this.playing = true;
  }

  pause(): void {
    this.wanted = false;
    if (!this.playing) return;
    this.offset = this.position;
    this.stopSources();
    this.playing = false;
  }

  seek(seconds: number): void {
    const wasPlaying = this.playing;
    this.pause();
    this.offset = Math.max(0, Math.min(seconds, this.duration));
    if (wasPlaying) void this.play();
  }

  setLoop(loop: { start: number; end: number } | null): void {
    const position = this.position;
    this.loop = loop && loop.end - loop.start > 0.05 ? loop : null;
    if (this.playing) this.seek(position);
  }

  /** Playback reached the end (no loop): stop and rewind. */
  ended(): boolean {
    if (!this.playing || this.loop) return false;
    if (this.position < this.duration) return false;
    this.pause();
    this.offset = 0;
    return true;
  }

  private stopSources(): void {
    for (const track of this.tracks.values()) {
      track.source?.stop();
      track.source?.disconnect();
      track.source = null;
    }
  }

  async close(): Promise<void> {
    this.stopSources();
    this.tracks.clear();
    await this.context.close();
  }
}
