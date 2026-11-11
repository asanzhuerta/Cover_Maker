/**
 * Preview player (ADR-007): every track of a song plays from one AudioContext
 * and every source is started with the same `start(t)` time, which keeps them
 * sample-aligned. Each track has a left and a right gain (fader and pan);
 * gains change with short ramps to avoid clicks. Tracks are decoded on
 * demand; a track added while playing joins at the same position. The master
 * bus feeds two analysers for the output meter.
 *
 * Practice (ADR-012): every source plays at `rate` (tempo), and one
 * Signalsmith Stretch node on the summed bus moves the pitch back (and by the
 * user's shift). The stretch is only in the chain while it has work to do.
 */

import type { StretchNode } from "signalsmith-stretch";
import { wrapPosition, type Stereo } from "./mixer";
import { ACCENT_HZ, CLICK_HZ, CLICK_SECONDS, CLICK_DECAY } from "./practice";
import { TONALITY_HZ, createStretch } from "./stretch";

const RAMP_SECONDS = 0.015;
const METER_WINDOW = 2048;

interface Track {
  buffer: AudioBuffer;
  input: ChannelSplitterNode;
  gains: [GainNode, GainNode];
  source: AudioBufferSourceNode | null;
}

export class Player {
  readonly context: AudioContext;
  private tracks = new Map<string, Track>();
  private targets = new Map<string, Stereo>();
  private master: GainNode;
  /** Sum of every track, before the stretch. */
  private bus: GainNode;
  private stretch: StretchNode | null = null;
  private stretchLoading: Promise<StretchNode> | null = null;
  private throughStretch = false;
  private shift = 0;
  /** Tempo factor: every source plays this many times faster. */
  rate = 1;
  private analysers: [AnalyserNode, AnalyserNode];
  private samples = new Float32Array(METER_WINDOW);
  /** Context time at which `offset` was playing (only while playing). */
  private startedAt = 0;
  private offset = 0;
  private loop: { start: number; end: number } | null = null;
  private wanted = false;
  playing = false;
  duration = 0;

  constructor(sampleRate?: number) {
    this.context = new AudioContext(sampleRate ? { sampleRate } : undefined);
    this.master = this.context.createGain();
    this.master.connect(this.context.destination);
    this.bus = this.context.createGain();
    this.bus.connect(this.master);
    const split = this.context.createChannelSplitter(2);
    this.master.connect(split);
    this.analysers = [
      this.context.createAnalyser(),
      this.context.createAnalyser(),
    ];
    this.analysers.forEach((analyser, channel) => {
      analyser.fftSize = METER_WINDOW;
      split.connect(analyser, channel);
    });
  }

  has(id: string): boolean {
    return this.tracks.has(id);
  }

  /** Decode a track (encoded file bytes) and connect it, silent until set. */
  async add(id: string, bytes: ArrayBuffer): Promise<void> {
    if (this.tracks.has(id)) return;
    const buffer = await this.context.decodeAudioData(bytes);
    this.addBuffer(id, buffer);
  }

  /** Samples for a generated track (the click), at the context's rate. */
  addSamples(id: string, samples: Float32Array): void {
    if (this.tracks.has(id) || samples.length === 0) return;
    const buffer = this.context.createBuffer(
      1,
      samples.length,
      this.context.sampleRate,
    );
    buffer.copyToChannel(new Float32Array(samples), 0);
    this.addBuffer(id, buffer);
  }

  private addBuffer(id: string, buffer: AudioBuffer): void {
    if (this.tracks.has(id)) return;
    const input = this.context.createChannelSplitter(2);
    const merge = this.context.createChannelMerger(2);
    const target = this.targets.get(id) ?? [0, 0];
    const gains: [GainNode, GainNode] = [
      this.context.createGain(),
      this.context.createGain(),
    ];
    gains.forEach((gain, channel) => {
      gain.gain.value = target[channel];
      // A mono file feeds both sides.
      input.connect(gain, buffer.numberOfChannels > 1 ? channel : 0);
      gain.connect(merge, 0, channel);
    });
    merge.connect(this.bus);
    const track: Track = { buffer, input, gains, source: null };
    this.tracks.set(id, track);
    this.duration = Math.max(this.duration, buffer.duration);
    if (this.playing) {
      const at = this.context.currentTime + 0.05;
      this.startSource(track, at, this.positionAt(at));
    }
  }

  /** Set a track's gain, the same on both sides or as a left/right pair. */
  setGain(id: string, value: number | Stereo): void {
    const pair: Stereo = typeof value === "number" ? [value, value] : value;
    this.targets.set(id, pair);
    const track = this.tracks.get(id);
    if (!track) return;
    const now = this.context.currentTime;
    track.gains.forEach((gain, channel) => {
      gain.gain.cancelScheduledValues(now);
      gain.gain.setTargetAtTime(pair[channel], now, RAMP_SECONDS / 3);
    });
  }

  /** Peak of the output over the last few milliseconds, per channel. */
  outputPeaks(): Stereo {
    const peaks = this.analysers.map((analyser) => {
      analyser.getFloatTimeDomainData(this.samples);
      let peak = 0;
      for (const sample of this.samples)
        peak = Math.max(peak, Math.abs(sample));
      return peak;
    });
    return [peaks[0], peaks[1]];
  }

  get position(): number {
    return this.playing
      ? this.positionAt(this.context.currentTime)
      : this.offset;
  }

  private positionAt(time: number): number {
    // Before `startedAt` (count-in) the song has not moved yet.
    const raw = this.offset + Math.max(0, time - this.startedAt) * this.rate;
    return Math.max(0, Math.min(wrapPosition(raw, this.loop), this.duration));
  }

  private startSource(track: Track, at: number, position: number): void {
    const source = this.context.createBufferSource();
    source.buffer = track.buffer;
    source.playbackRate.value = this.rate;
    if (this.loop) {
      source.loop = true;
      source.loopStart = this.loop.start;
      source.loopEnd = this.loop.end;
    }
    source.connect(track.input);
    source.start(at, Math.min(position, track.buffer.duration));
    track.source = source;
  }

  /**
   * Start playback. With `countIn` (seconds), one bar of clicks plays first
   * and the song starts right after it.
   */
  async play(countIn = 0, beats = 4): Promise<void> {
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
    let at = this.context.currentTime + 0.05;
    if (countIn > 0) {
      for (let beat = 0; beat < beats; beat++)
        this.blip(at + (beat * countIn) / beats, beat === 0);
      at += countIn;
    }
    for (const track of this.tracks.values())
      this.startSource(track, at, this.offset);
    this.startedAt = at;
    this.playing = true;
  }

  /** One count-in click, through the same bus (and latency) as the song. */
  private blip(at: number, accent: boolean): void {
    const osc = this.context.createOscillator();
    const gain = this.context.createGain();
    osc.frequency.value = accent ? ACCENT_HZ : CLICK_HZ;
    gain.gain.setValueAtTime(accent ? 0.8 : 0.5, at);
    gain.gain.setTargetAtTime(0, at, 1 / CLICK_DECAY);
    osc.connect(gain).connect(this.bus);
    osc.start(at);
    osc.stop(at + CLICK_SECONDS * 4);
    osc.onended = () => gain.disconnect();
  }

  /** Play every source `rate` times faster (the stretch fixes the pitch). */
  setRate(rate: number): void {
    if (rate === this.rate) return;
    const now = this.context.currentTime;
    if (this.playing) {
      this.offset = this.positionAt(now);
      this.startedAt = Math.max(now, this.startedAt);
    }
    this.rate = rate;
    for (const track of this.tracks.values())
      track.source?.playbackRate.setValueAtTime(rate, now);
  }

  /** Semitones the master-bus stretch shifts by (0 takes it out of the chain). */
  async setShift(semitones: number): Promise<void> {
    this.shift = semitones;
    const needed = Math.abs(semitones) > 1e-4;
    if (needed && !this.stretch) {
      this.stretchLoading ??= createStretch(this.context);
      this.stretch = await this.stretchLoading;
    }
    const stretch = this.stretch;
    if (!stretch) return;
    // A later call may have changed the shift while the worklet loaded.
    const shift = this.shift;
    const active = Math.abs(shift) > 1e-4;
    await stretch.schedule({
      active,
      semitones: shift,
      tonalityHz: TONALITY_HZ,
    });
    if (active === this.throughStretch) return;
    this.bus.disconnect();
    if (active) {
      this.bus.connect(stretch);
      stretch.connect(this.master);
    } else {
      stretch.disconnect();
      this.bus.connect(this.master);
    }
    this.throughStretch = active;
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
    this.stretch?.disconnect();
    this.tracks.clear();
    await this.context.close();
  }
}
