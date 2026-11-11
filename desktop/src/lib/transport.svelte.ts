/**
 * The song loaded in the preview player (ADR-007). It lives outside any page,
 * so playback goes on while the user moves around the app: the mixer page and
 * the transport dock are two views of this state.
 */
import type { Schemas } from "./api/client";
import { connection } from "./connection.svelte";
import { baseUrl } from "./engine";
import { t } from "./i18n.svelte";
import {
  MEMORY_BUDGET_MB,
  REDUCED_RATE,
  dbToGain,
  decodedMb,
  effectiveGains,
  nodeGains,
  panGains,
  pans,
  stemsNeeded,
  wavSeconds,
  type Residual,
  type StemControl,
} from "./mixer";
import {
  downsample,
  envelopePeak,
  envelopePoints,
  meterStep,
  silentMeter,
  toDb,
  type MeterState,
} from "./meter";
import { Player } from "./player";
import {
  clampTempo,
  countInSeconds,
  freshTrainer,
  loopWrapped,
  nextMarkerName,
  pitchCorrection,
  renderClick,
  sectionRegion,
  snapRegion,
  sortMarkers,
  trainerTempo,
  type Marker,
} from "./practice";
import { mixerStems, type Stem } from "./stems";

export const MIX = "mix";
export const CLICK = "click";
const WAVE_POINTS = 900;

export interface Region {
  start: number;
  end: number;
}

export const freshControl = (): StemControl => ({
  db: 0,
  muted: false,
  soloed: false,
  pan: 0,
});

export const freshPractice = () => ({
  /** Whole semitones, -12..+12. */
  semitones: 0,
  /** Fine tuning, -50..+50 cents. */
  cents: 0,
  /** Tempo factor, 0.5..1.5. */
  tempo: 1,
  click: false,
  clickDb: -6,
  countIn: false,
  snap: true,
});

export const transport = $state({
  itemId: null as number | null,
  preview: null as Schemas["PreviewOut"] | null,
  loading: false,
  failure: "",
  memoryNote: "",
  /** Waveform per track ([min, max] pairs). */
  peaks: {} as Record<string, number[][]>,
  controls: {} as Record<string, StemControl>,
  decoding: {} as Record<string, boolean>,
  residual: "keep" as Residual,
  /** A/B: true plays the untouched original. */
  original: false,
  playing: false,
  position: 0,
  duration: 0,
  looping: false,
  loop: null as Region | null,
  /** Lane the keyboard shortcuts act on (index in `lanes()`). */
  selected: 0,
  /** Meter per stem, plus `L` and `R` for the output. */
  meters: {} as Record<string, MeterState>,
  /** Tuning, key and beat grid from the engine (null until it answers). */
  analysis: null as Schemas["AnalysisOut"] | null,
  markers: [] as Marker[],
  practice: freshPractice(),
  trainer: freshTrainer(),
  /** Loop passes since the trainer (or the loop) started. */
  passes: 0,
  /** True while the count-in bar plays. */
  counting: false,
});

// Plain values, not UI state.
let player: Player | null = null;
let envelopes: Record<string, number[][]> = {};
let timer: ReturnType<typeof setInterval> | null = null;
let lastTick = 0;
let lastPosition = 0;

/**
 * Stems of the loaded song, in the usual order. Lead and backing vocals take
 * the place of the vocals when the song has them.
 */
export function lanes(): Stem[] {
  const preview = transport.preview;
  return preview ? mixerStems(Object.keys(preview.stems)) : [];
}

async function fetchAudio(sha: string): Promise<ArrayBuffer> {
  const info = connection.info!;
  // The token goes in a header, never in the URL (it would end up in logs).
  const response = await fetch(`${baseUrl(info)}/assets/${sha}`, {
    headers: { Authorization: `Bearer ${info.token}` },
  });
  if (!response.ok) throw new Error(`audio ${response.status}`);
  return response.arrayBuffer();
}

async function loadEnvelope(id: string, sha: string, points: number) {
  const { data } = await connection.api!.GET("/assets/{sha}/peaks", {
    params: { path: { sha }, query: { points } },
  });
  if (!data) return;
  envelopes[id] = data.peaks;
  transport.peaks[id] = downsample(data.peaks, WAVE_POINTS);
}

/** Load a song into the player, unless it is already the loaded one. */
export async function openItem(itemId: number): Promise<void> {
  if (transport.itemId === itemId) return;
  await closeSong();
  if (!connection.api) return;
  transport.itemId = itemId;
  transport.loading = true;
  const { data, error } = await connection.api.GET("/items/{item_id}/preview", {
    params: { path: { item_id: itemId } },
  });
  if (transport.itemId !== itemId) return;
  if (!data) {
    transport.failure = error ? t("mixer.noPreview") : "";
    transport.loading = false;
    return;
  }
  transport.preview = data;
  void loadAnalysis(itemId);
  // One control per lane: with lead and backing vocals, the vocals have none,
  // so they are never played on top of their parts.
  transport.controls = Object.fromEntries(
    mixerStems(Object.keys(data.stems)).map((stem) => [stem, freshControl()]),
  );
  transport.meters = {};
  try {
    const bytes = await fetchAudio(data.mix);
    const seconds = wavSeconds(bytes.byteLength);
    const points = envelopePoints(seconds);
    void loadEnvelope(MIX, data.mix, points);
    for (const [stem, sha] of Object.entries(data.stems))
      void loadEnvelope(stem, sha, points);
    const tracks = 1 + Object.keys(data.stems).length;
    const reduced = decodedMb(seconds, tracks, 44_100) > MEMORY_BUDGET_MB;
    if (reduced) {
      const mb = Math.round(decodedMb(seconds, tracks, REDUCED_RATE));
      transport.memoryNote = t("mixer.memory").replace("{mb}", String(mb));
    }
    const next = new Player(reduced ? REDUCED_RATE : undefined);
    await next.add(MIX, bytes);
    if (transport.itemId !== itemId) {
      void next.close();
      return;
    }
    player = next;
    transport.duration = player.duration;
    applyGains();
    applyPractice();
    startTimer();
  } catch (failure) {
    transport.failure = String(failure);
  }
  transport.loading = false;
}

/** Stop playback and forget the loaded song. */
export async function closeSong(): Promise<void> {
  const old = player;
  player = null;
  envelopes = {};
  Object.assign(transport, {
    itemId: null,
    preview: null,
    loading: false,
    failure: "",
    memoryNote: "",
    peaks: {},
    controls: {},
    decoding: {},
    residual: "keep",
    original: false,
    playing: false,
    position: 0,
    duration: 0,
    looping: false,
    loop: null,
    selected: 0,
    meters: {},
    analysis: null,
    markers: [],
    practice: freshPractice(),
    trainer: freshTrainer(),
    passes: 0,
    counting: false,
  });
  await old?.close();
}

/** Ask the engine for the song's analysis (computed now for older songs). */
async function loadAnalysis(itemId: number): Promise<void> {
  if (!connection.api) return;
  const { data } = await connection.api.GET("/items/{item_id}/analysis", {
    params: { path: { item_id: itemId } },
  });
  if (transport.itemId !== itemId || !data) return;
  transport.analysis = data;
  transport.markers = sortMarkers(data.markers);
}

function applyGains() {
  if (!player) return;
  const values = nodeGains(
    effectiveGains(transport.controls),
    transport.residual,
    transport.original,
    pans(transport.controls),
  );
  player.setGain(MIX, values.mix);
  for (const [stem, value] of Object.entries(values.stems))
    player.setGain(stem, value);
  player.setGain(
    CLICK,
    transport.practice.click ? dbToGain(transport.practice.clickDb) : 0,
  );
}

/** Generate the click track from the beat grid the first time it is wanted. */
function ensureClick() {
  const beats = transport.analysis?.beats ?? [];
  if (!player || !transport.practice.click || player.has(CLICK)) return;
  if (beats.length === 0) return;
  const rate = player.context.sampleRate;
  player.addSamples(
    CLICK,
    renderClick(
      rate,
      Math.round(player.duration * rate),
      beats,
      transport.analysis?.downbeats ?? [],
    ),
  );
}

function applyPractice() {
  if (!player) return;
  const { tempo, semitones, cents } = transport.practice;
  player.setRate(tempo);
  void player
    .setShift(pitchCorrection(tempo, semitones, cents))
    .catch((failure: unknown) => (transport.failure = String(failure)));
}

// Decode a stem only once the current settings need it (ADR-007).
function decodeNeeded() {
  if (!player || !transport.preview) return;
  const needed = stemsNeeded(
    effectiveGains(transport.controls),
    transport.residual,
    pans(transport.controls),
  );
  for (const stem of needed) {
    if (player.has(stem) || transport.decoding[stem]) continue;
    void decodeStem(stem);
  }
}

async function decodeStem(stem: string) {
  const target = player;
  const preview = transport.preview;
  if (!target || !preview) return;
  transport.decoding[stem] = true;
  try {
    await target.add(stem, await fetchAudio(preview.stems[stem]));
    if (target === player) applyGains();
  } catch (failure) {
    transport.failure = String(failure);
  }
  transport.decoding[stem] = false;
}

if (typeof window !== "undefined") {
  $effect.root(() => {
    $effect(() => {
      // Track every control, the residual and A/B.
      void JSON.stringify(transport.controls);
      void [transport.residual, transport.original];
      void [transport.practice.click, transport.practice.clickDb];
      void transport.analysis;
      ensureClick();
      applyGains();
      decodeNeeded();
    });
    $effect(() => {
      void [
        transport.practice.tempo,
        transport.practice.semitones,
        transport.practice.cents,
      ];
      applyPractice();
    });
  });
}

function stepMeters(dt: number) {
  const playing = transport.playing && player !== null;
  const gains = effectiveGains(transport.controls);
  const next: Record<string, MeterState> = {};
  let active = false;
  for (const stem of lanes()) {
    let level = 0;
    if (playing && !transport.original) {
      const [left, right] = panGains(transport.controls[stem]?.pan ?? 0);
      level =
        envelopePeak(
          envelopes[stem] ?? [],
          transport.duration,
          lastPosition,
          transport.position,
        ) *
        (gains[stem] ?? 0) *
        Math.max(left, right);
    }
    const meter = meterStep(
      transport.meters[stem] ?? silentMeter(),
      toDb(level),
      dt,
    );
    next[stem] = meter;
    active ||= meter.peak > silentMeter().peak;
  }
  const output = playing && player ? player.outputPeaks() : [0, 0];
  (["L", "R"] as const).forEach((side, channel) => {
    const meter = meterStep(
      transport.meters[side] ?? silentMeter(),
      toDb(output[channel]),
      dt,
    );
    next[side] = meter;
    active ||= meter.peak > silentMeter().peak;
  });
  if (active || Object.keys(transport.meters).length === 0)
    transport.meters = next;
}

function tick() {
  const now = performance.now();
  const dt = lastTick ? Math.min(0.25, (now - lastTick) / 1000) : 0;
  lastTick = now;
  if (!player) return;
  if (player.ended()) transport.playing = false;
  lastPosition = transport.position;
  transport.position = player.position;
  if (
    transport.looping &&
    loopWrapped(lastPosition, transport.position, transport.loop)
  )
    passDone();
  stepMeters(dt);
}

// A timer, not requestAnimationFrame: the end of the song must still be
// noticed while the window is hidden.
function startTimer() {
  if (timer) return;
  timer = setInterval(tick, 33);
}

export async function toggle(): Promise<void> {
  if (!player) return;
  if (player.playing) player.pause();
  else {
    const bpm = transport.analysis?.bpm ?? 0;
    const countIn = transport.practice.countIn
      ? countInSeconds(bpm, transport.practice.tempo)
      : 0;
    transport.counting = countIn > 0;
    const playing = player.play(countIn);
    if (countIn > 0)
      setTimeout(() => (transport.counting = false), countIn * 1000 + 50);
    await playing;
  }
  transport.playing = player.playing;
}

/** One more pass of the loop: the speed trainer may raise the tempo. */
function passDone() {
  transport.passes += 1;
  const trainer = transport.trainer;
  if (trainer.on)
    transport.practice.tempo = trainerTempo(trainer, transport.passes);
}

export function setTempo(tempo: number): void {
  transport.practice.tempo = clampTempo(Math.round(tempo * 100) / 100);
}

/** Start or stop the speed trainer; it loops the current region. */
export function setTrainer(on: boolean): void {
  transport.trainer.on = on;
  transport.passes = 0;
  if (!on) return;
  transport.practice.tempo = trainerTempo(transport.trainer, 0);
  if (!transport.looping) setLooping(true);
}

/** Fine-tune so the song sits on A440 (e.g. a recording 30 cents flat). */
export function tuneToA440(): void {
  const offset = transport.analysis?.tuning_cents ?? 0;
  transport.practice.cents = Math.max(-50, Math.min(50, -Math.round(offset)));
}

export function resetPractice(): void {
  const keep = {
    click: transport.practice.click,
    snap: transport.practice.snap,
  };
  Object.assign(transport.practice, freshPractice(), keep);
  transport.trainer.on = false;
  transport.passes = 0;
}

// ------------------------------------------------------------ markers

async function saveMarkers() {
  const itemId = transport.itemId;
  if (!connection.api || itemId === null) return;
  const { data } = await connection.api.PUT("/items/{item_id}/markers", {
    params: { path: { item_id: itemId } },
    body: { markers: transport.markers },
  });
  if (data && transport.itemId === itemId) transport.markers = data;
}

export function addMarker(base: string, name?: string): void {
  const marker = {
    name: (name ?? "").trim() || nextMarkerName(transport.markers, base),
    time: Math.round(transport.position * 1000) / 1000,
  };
  transport.markers = sortMarkers([...transport.markers, marker]);
  void saveMarkers();
}

export function renameMarker(index: number, name: string): void {
  const marker = transport.markers[index];
  if (!marker || !name.trim()) return;
  marker.name = name.trim().slice(0, 40);
  void saveMarkers();
}

export function removeMarker(index: number): void {
  transport.markers = transport.markers.filter((_, i) => i !== index);
  void saveMarkers();
}

/** Loop from a marker to the next one. */
export function loopSection(index: number): void {
  const region = sectionRegion(transport.markers, index, transport.duration);
  if (!region) return;
  transport.looping = true;
  transport.loop = region;
  transport.passes = 0;
  player?.setLoop(region);
  seek(region.start);
}

export function seek(seconds: number): void {
  const at = Math.max(0, Math.min(seconds, transport.duration));
  player?.seek(at);
  transport.position = at;
  lastPosition = at;
}

export function seekBy(seconds: number): void {
  seek(transport.position + seconds);
}

export function setLoop(region: Region | null): void {
  const bars = transport.analysis?.downbeats ?? [];
  if (region && transport.practice.snap && bars.length > 0)
    region = snapRegion(region, bars, transport.duration);
  if (
    region?.start !== transport.loop?.start ||
    region?.end !== transport.loop?.end
  )
    transport.passes = 0;
  transport.loop = region;
  player?.setLoop(transport.looping ? region : null);
}

export function setLooping(on: boolean): void {
  transport.looping = on;
  if (on && !transport.loop)
    transport.loop = { start: 0, end: transport.duration };
  player?.setLoop(on ? transport.loop : null);
}

export function toggleLoop(): void {
  setLooping(!transport.looping);
}

export function toggleOriginal(): void {
  transport.original = !transport.original;
}

export function toggleMute(stem: string): void {
  const control = transport.controls[stem];
  if (control) control.muted = !control.muted;
}

export function toggleSolo(stem: string): void {
  const control = transport.controls[stem];
  if (control) control.soloed = !control.soloed;
}

export function selectLane(index: number): void {
  const count = lanes().length;
  if (count === 0) return;
  transport.selected = Math.max(0, Math.min(count - 1, index));
}

export function resetMix(): void {
  for (const control of Object.values(transport.controls))
    Object.assign(control, freshControl());
  transport.residual = "keep";
  transport.original = false;
}
