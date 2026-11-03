<script lang="ts">
  import { onDestroy } from "svelte";
  import { resolve } from "$app/paths";
  import { page } from "$app/state";
  import { errorMessage, type Schemas } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import { connection, isTauri } from "$lib/connection.svelte";
  import { baseUrl } from "$lib/engine";
  import { t } from "$lib/i18n.svelte";
  import {
    MAX_DB,
    MEMORY_BUDGET_MB,
    MIN_DB,
    REDUCED_RATE,
    decodedMb,
    effectiveGains,
    formatDb,
    formatTime,
    nodeGains,
    peaksPath,
    stemsNeeded,
    wavSeconds,
    type Residual,
    type StemControl,
  } from "$lib/mixer";
  import { Player } from "$lib/player";
  import { STEMS, stemColor, type Stem } from "$lib/stems";

  const MIX = "mix";
  const PEAK_POINTS = 900;
  const WAVE_W = 900;

  const itemId = $derived(Number(page.params.item));

  let preview = $state<Schemas["PreviewOut"] | null>(null);
  let failure = $state("");
  let loading = $state(true);
  let memoryNote = $state("");
  let peaks = $state<Record<string, number[][]>>({});
  let controls = $state<Record<string, StemControl>>({});
  let decoding = $state<Record<string, boolean>>({});
  let residual = $state<Residual>("keep");
  let original = $state(false);
  let playing = $state(false);
  let position = $state(0);
  let duration = $state(0);
  let looping = $state(false);
  let loop = $state<{ start: number; end: number } | null>(null);
  let rendering = $state(false);
  let rendered = $state<Schemas["RenderOut"] | null>(null);
  let renderError = $state("");

  // Raw state: effects re-run once the player exists, without proxying it.
  let player = $state.raw<Player | null>(null);

  const stems = $derived(
    preview
      ? (STEMS.filter((stem) => stem in preview!.stems) as Stem[])
      : ([] as Stem[]),
  );
  const gains = $derived(effectiveGains(controls));

  async function fetchAudio(sha: string): Promise<ArrayBuffer> {
    const info = connection.info!;
    // The token goes in a header, never in the URL (it would end up in logs).
    const response = await fetch(`${baseUrl(info)}/assets/${sha}`, {
      headers: { Authorization: `Bearer ${info.token}` },
    });
    if (!response.ok) throw new Error(`audio ${response.status}`);
    return response.arrayBuffer();
  }

  async function loadPeaks(id: string, sha: string) {
    const { data } = await connection.api!.GET("/assets/{sha}/peaks", {
      params: { path: { sha }, query: { points: PEAK_POINTS } },
    });
    if (data) peaks[id] = data.peaks;
  }

  async function load() {
    if (!connection.api) return;
    const { data, error } = await connection.api.GET(
      "/items/{item_id}/preview",
      { params: { path: { item_id: itemId } } },
    );
    if (!data) {
      failure = error ? t("mixer.noPreview") : "";
      loading = false;
      return;
    }
    preview = data;
    controls = Object.fromEntries(
      Object.keys(data.stems).map((stem) => [
        stem,
        { db: 0, muted: false, soloed: false },
      ]),
    );
    void loadPeaks(MIX, data.mix);
    for (const [stem, sha] of Object.entries(data.stems))
      void loadPeaks(stem, sha);
    try {
      const bytes = await fetchAudio(data.mix);
      const seconds = wavSeconds(bytes.byteLength);
      const tracks = 1 + Object.keys(data.stems).length;
      const full = decodedMb(seconds, tracks, 44_100);
      const reduced = full > MEMORY_BUDGET_MB;
      if (reduced) {
        const mb = Math.round(decodedMb(seconds, tracks, REDUCED_RATE));
        memoryNote = t("mixer.memory").replace("{mb}", String(mb));
      }
      player = new Player(reduced ? REDUCED_RATE : undefined);
      await player.add(MIX, bytes);
      duration = player.duration;
      applyGains();
    } catch (error) {
      failure = String(error);
    }
    loading = false;
  }

  $effect(() => {
    if (connection.status === "ready" && !preview && loading) void load();
  });

  // Decode a stem only once the current settings need it (ADR-007).
  $effect(() => {
    if (!player || !preview) return;
    for (const stem of stemsNeeded(gains, residual)) {
      if (player.has(stem) || decoding[stem]) continue;
      void decodeStem(stem);
    }
  });

  async function decodeStem(stem: string) {
    if (!player || !preview) return;
    decoding[stem] = true;
    try {
      await player.add(stem, await fetchAudio(preview.stems[stem]));
      applyGains();
    } catch (error) {
      failure = String(error);
    }
    decoding[stem] = false;
  }

  function applyGains() {
    if (!player) return;
    const values = nodeGains(gains, residual, original);
    player.setGain(MIX, values.mix);
    for (const [stem, value] of Object.entries(values.stems))
      player.setGain(stem, value);
  }

  $effect(() => {
    void [gains, residual, original];
    applyGains();
  });

  function tick() {
    if (player) {
      if (player.ended()) playing = false;
      position = player.position;
    }
  }
  // A timer, not requestAnimationFrame: the end of the song must still be
  // noticed while the window is hidden.
  const timer = setInterval(tick, 33);

  async function toggle() {
    if (!player) return;
    if (player.playing) player.pause();
    else await player.play();
    playing = player.playing;
  }

  function seek(seconds: number) {
    player?.seek(seconds);
    position = seconds;
  }

  function setLoop(region: { start: number; end: number } | null) {
    loop = region;
    player?.setLoop(looping ? region : null);
  }

  function toggleLoop() {
    looping = !looping;
    if (looping && !loop) loop = { start: 0, end: duration };
    player?.setLoop(looping ? loop : null);
  }

  // Click to seek; drag to choose the loop region.
  let dragFrom: number | null = null;
  function timeAt(event: PointerEvent): number {
    const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const share = Math.min(
      1,
      Math.max(0, (event.clientX - box.left) / box.width),
    );
    return share * duration;
  }
  function pointerDown(event: PointerEvent) {
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    dragFrom = timeAt(event);
  }
  function pointerMove(event: PointerEvent) {
    if (dragFrom === null) return;
    const at = timeAt(event);
    if (Math.abs(at - dragFrom) < duration / 200) return;
    looping = true;
    setLoop({ start: Math.min(dragFrom, at), end: Math.max(dragFrom, at) });
  }
  function pointerUp(event: PointerEvent) {
    if (dragFrom === null) return;
    const at = timeAt(event);
    if (Math.abs(at - dragFrom) < duration / 200) seek(at);
    dragFrom = null;
  }

  function solo(stem: string) {
    controls[stem].soloed = !controls[stem].soloed;
  }

  function reset() {
    for (const control of Object.values(controls)) {
      control.db = 0;
      control.muted = false;
      control.soloed = false;
    }
    residual = "keep";
    original = false;
  }

  async function render() {
    if (!connection.api) return;
    rendering = true;
    rendered = null;
    renderError = "";
    const { data, error } = await connection.api.POST(
      "/items/{item_id}/render",
      {
        params: { path: { item_id: itemId } },
        body: { gains: gains as Record<Stem, number>, residual },
      },
    );
    rendering = false;
    if (data) rendered = data;
    else renderError = errorMessage(error);
  }

  async function reveal(path: string) {
    const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
    await revealItemInDir(path);
  }

  function keydown(event: KeyboardEvent) {
    const target = event.target as HTMLElement;
    if (event.code !== "Space" || target.closest("input, button")) return;
    event.preventDefault();
    void toggle();
  }

  onDestroy(() => {
    clearInterval(timer);
    void player?.close();
  });

  const head = $derived(duration ? (position / duration) * 100 : 0);
</script>

<svelte:window onkeydown={keydown} />

<header class="page-head">
  <div>
    <a class="back" href={resolve("/queue")}
      ><Icon name="arrowLeft" size={14} />{t("mixer.back")}</a
    >
    <h1>{t("mixer.title")}</h1>
    <p>{preview?.title ?? ""}</p>
  </div>
</header>

{#if loading}
  <div class="card muted" data-testid="mixer-loading">{t("mixer.loading")}</div>
{:else if !preview}
  <div class="card error" data-testid="mixer-missing">{failure}</div>
{:else}
  {#if failure}<p class="error">{failure}</p>{/if}
  {#if memoryNote}<p class="card note" data-testid="memory-note">
      {memoryNote}
    </p>{/if}

  <section class="card transport">
    <button
      class="primary play"
      onclick={toggle}
      aria-label={playing ? t("mixer.pause") : t("mixer.play")}
      data-testid="play"
      ><Icon name={playing ? "pause" : "play"} size={20} /></button
    >
    <span class="time" data-testid="time"
      >{formatTime(position)} / {formatTime(duration)}</span
    >
    <button
      class="small"
      class:on={looping}
      onclick={toggleLoop}
      title={t("mixer.loopHint")}
      data-testid="loop"><Icon name="loop" size={14} />{t("mixer.loop")}</button
    >
    <div class="ab" role="group" title={t("mixer.abHint")}>
      <button
        class="small"
        class:on={!original}
        onclick={() => (original = false)}
        data-testid="ab-custom">B · {t("mixer.custom")}</button
      >
      <button
        class="small"
        class:on={original}
        onclick={() => (original = true)}
        data-testid="ab-original">A · {t("mixer.original")}</button
      >
    </div>
    <span class="spacer"></span>
    <label class="residual">
      <input
        type="checkbox"
        checked={residual === "keep"}
        onchange={(event) =>
          (residual = event.currentTarget.checked ? "keep" : "drop")}
        data-testid="residual"
      />
      {t("mixer.residual")}
    </label>
    <button class="small ghost" onclick={reset}
      ><Icon name="reset" size={14} />{t("mixer.reset")}</button
    >
  </section>

  <section class="card lanes">
    <div class="lane overview">
      <div class="label">
        <Icon name="mix" size={16} />{t("mixer.original")}
      </div>
      <div class="controls muted loop-range" data-testid="loop-range">
        {#if looping && loop}<Icon name="loop" size={13} />{formatTime(
            loop.start,
          )}–{formatTime(loop.end)}{/if}
      </div>
      <div
        class="wave"
        role="slider"
        tabindex="0"
        aria-label={t("mixer.loopHint")}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        aria-valuenow={Math.round(position)}
        onpointerdown={pointerDown}
        onpointermove={pointerMove}
        onpointerup={pointerUp}
        data-testid="overview"
      >
        <svg viewBox="0 0 {WAVE_W} 64" preserveAspectRatio="none">
          <path d={peaksPath(peaks[MIX] ?? [], WAVE_W, 64)} />
        </svg>
        {#if looping && loop && duration}
          <div
            class="loop"
            style="left: {(loop.start / duration) * 100}%; width: {((loop.end -
              loop.start) /
              duration) *
              100}%"
          ></div>
        {/if}
        <div class="head" style="left: {head}%"></div>
      </div>
    </div>

    {#each stems as stem (stem)}
      {@const control = controls[stem]}
      {@const audible = (gains[stem] ?? 0) > 0}
      <div
        class="lane"
        class:silent={!audible || original}
        style="--stem: {stemColor(stem)}"
        data-testid="lane-{stem}"
      >
        <div class="label">
          <span class="stem-icon"><Icon name={stem} size={16} /></span>
          {t(`stem.${stem}`)}
          {#if decoding[stem]}<span class="muted small-note"
              >{t("mixer.decoding")}</span
            >{/if}
        </div>
        <div class="controls">
          <button
            class="small toggle"
            class:on={control.muted}
            aria-pressed={control.muted}
            title={t("mixer.mute")}
            aria-label="{t('mixer.mute')} {t(`stem.${stem}`)}"
            onclick={() => (control.muted = !control.muted)}
            data-testid="mute-{stem}">M</button
          >
          <button
            class="small toggle solo"
            class:on={control.soloed}
            aria-pressed={control.soloed}
            title={t("mixer.solo")}
            aria-label="{t('mixer.solo')} {t(`stem.${stem}`)}"
            onclick={() => solo(stem)}
            data-testid="solo-{stem}">S</button
          >
          <input
            type="range"
            min={MIN_DB}
            max={MAX_DB}
            step="0.5"
            bind:value={control.db}
            ondblclick={() => (control.db = 0)}
            aria-label="{t('mixer.volume')} {t(`stem.${stem}`)}"
            data-testid="volume-{stem}"
          />
          <span class="db">{formatDb(control.db)}</span>
        </div>
        <div
          class="wave"
          role="presentation"
          onpointerdown={pointerDown}
          onpointermove={pointerMove}
          onpointerup={pointerUp}
        >
          <svg viewBox="0 0 {WAVE_W} 40" preserveAspectRatio="none">
            <path d={peaksPath(peaks[stem] ?? [], WAVE_W, 40)} />
          </svg>
          <div class="head" style="left: {head}%"></div>
        </div>
      </div>
    {/each}
  </section>

  <section class="card export">
    <button
      class="primary"
      onclick={render}
      disabled={rendering}
      data-testid="render"
      ><Icon name="download" size={16} />{rendering
        ? t("mixer.rendering")
        : t("mixer.render")}</button
    >
    {#if rendered}
      <div class="rendered" data-testid="rendered">
        <span class="muted">{t("mixer.rendered")}</span>
        <code>{rendered.path}</code>
        {#if rendered.gain_db < -0.05}<span class="badge warn"
            >{t("mixer.clipped").replace(
              "{db}",
              Math.abs(rendered.gain_db).toFixed(1),
            )}</span
          >{/if}
        {#if isTauri()}
          <button class="small" onclick={() => reveal(rendered!.path)}
            ><Icon name="folder" size={14} />{t("queue.open")}</button
          >
        {/if}
      </div>
    {/if}
    {#if renderError}<p class="error">{renderError}</p>{/if}
  </section>
{/if}

<style>
  .back {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    margin-bottom: 0.4rem;
    font-size: 0.85rem;
    text-decoration: none;
  }

  .note {
    border-color: color-mix(in srgb, var(--warn) 45%, var(--border));
    color: var(--warn);
    font-size: 0.9rem;
  }

  .transport,
  .export {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.7rem;
    margin-bottom: 0.9rem;
  }

  .play {
    width: 48px;
    height: 48px;
    padding: 0;
    border-radius: 50%;
  }

  .time {
    min-width: 7.5rem;
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }

  .ab {
    display: inline-flex;
    gap: 0.2rem;
  }

  button.on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--fg);
  }

  .spacer {
    flex: 1;
  }

  .residual {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.88rem;
  }

  .lanes {
    display: grid;
    gap: 0.45rem;
    margin-bottom: 0.9rem;
  }

  .lane {
    --stem: var(--accent);
    display: grid;
    grid-template-columns: 8.5rem 15rem minmax(0, 1fr);
    align-items: center;
    gap: 0.8rem;
    padding: 0.35rem 0.5rem;
    border-radius: 10px;
    background: var(--surface);
    border: 1px solid var(--border);
    transition: opacity 0.2s ease;
  }

  .lane.silent .wave path {
    opacity: 0.25;
  }

  .label {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-weight: 600;
    color: var(--stem);
  }

  .overview .label {
    color: var(--muted);
  }

  .stem-icon {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    background: color-mix(in srgb, var(--stem) 14%, transparent);
  }

  .loop-range {
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }

  .small-note {
    font-size: 0.75rem;
    font-weight: 400;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .toggle {
    width: 2rem;
    padding: 0.3rem 0;
    font-weight: 700;
  }

  .toggle.on {
    border-color: var(--danger);
    background: color-mix(in srgb, var(--danger) 18%, transparent);
  }

  .toggle.solo.on {
    border-color: var(--warn);
    background: color-mix(in srgb, var(--warn) 18%, transparent);
  }

  input[type="range"] {
    flex: 1;
    min-width: 0;
    accent-color: var(--stem);
  }

  .db {
    width: 4.4rem;
    font-size: 0.78rem;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    text-align: right;
  }

  .wave {
    position: relative;
    cursor: pointer;
    touch-action: none;
  }

  .wave svg {
    display: block;
    width: 100%;
    height: 40px;
  }

  .overview .wave svg {
    height: 64px;
  }

  .wave path {
    fill: var(--stem);
    opacity: 0.85;
    transition: opacity 0.2s ease;
  }

  .overview .wave path {
    fill: var(--muted);
    opacity: 0.6;
  }

  .head {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    margin-left: -1px;
    background: var(--fg);
    pointer-events: none;
  }

  .loop {
    position: absolute;
    top: 0;
    bottom: 0;
    background: var(--accent-soft);
    border-inline: 1px solid var(--accent);
    pointer-events: none;
  }

  .rendered {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.88rem;
  }

  code {
    overflow-wrap: anywhere;
  }
</style>
