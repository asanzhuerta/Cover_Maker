<script lang="ts">
  import { resolve } from "$app/paths";
  import { page } from "$app/state";
  import { errorMessage, type Schemas } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import Knob from "$lib/components/Knob.svelte";
  import Meter from "$lib/components/Meter.svelte";
  import { connection, isTauri } from "$lib/connection.svelte";
  import { t } from "$lib/i18n.svelte";
  import {
    MAX_DB,
    MIN_DB,
    effectiveGains,
    formatDb,
    formatPan,
    formatTime,
    pans,
    peaksPath,
  } from "$lib/mixer";
  import { stemColor, type Stem } from "$lib/stems";
  import {
    MIX,
    lanes,
    openItem,
    resetMix,
    seek,
    selectLane,
    setLoop,
    toggleMute,
    toggleSolo,
    transport,
  } from "$lib/transport.svelte";

  const WAVE_W = 900;

  const itemId = $derived(Number(page.params.item));

  let rendering = $state(false);
  let rendered = $state<Schemas["RenderOut"] | null>(null);
  let renderError = $state("");

  $effect(() => {
    if (connection.status === "ready") void openItem(itemId);
  });

  const stems = $derived(lanes());
  const gains = $derived(effectiveGains(transport.controls));
  const current = $derived(transport.itemId === itemId);
  const head = $derived(
    transport.duration ? (transport.position / transport.duration) * 100 : 0,
  );

  // Click to seek; drag to choose the loop region.
  let dragFrom: number | null = null;
  function timeAt(event: PointerEvent): number {
    const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const share = Math.min(
      1,
      Math.max(0, (event.clientX - box.left) / box.width),
    );
    return share * transport.duration;
  }
  function pointerDown(event: PointerEvent) {
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    dragFrom = timeAt(event);
  }
  function pointerMove(event: PointerEvent) {
    if (dragFrom === null) return;
    const at = timeAt(event);
    if (Math.abs(at - dragFrom) < transport.duration / 200) return;
    transport.looping = true;
    setLoop({ start: Math.min(dragFrom, at), end: Math.max(dragFrom, at) });
  }
  function pointerUp(event: PointerEvent) {
    if (dragFrom === null) return;
    const at = timeAt(event);
    if (Math.abs(at - dragFrom) < transport.duration / 200) seek(at);
    dragFrom = null;
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
        body: {
          gains: gains as Record<Stem, number>,
          pans: pans(transport.controls) as Record<Stem, number>,
          residual: transport.residual,
        },
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
</script>

<header class="page-head">
  <div>
    <a class="back" href={resolve("/queue")}
      ><Icon name="arrowLeft" size={14} />{t("mixer.back")}</a
    >
    <h1>{t("mixer.title")}</h1>
    <p>{(current && transport.preview?.title) || ""}</p>
  </div>
  {#if current && transport.preview}
    <div class="row tools">
      <button
        class="small led-button"
        aria-pressed={transport.residual === "keep"}
        onclick={() =>
          (transport.residual =
            transport.residual === "keep" ? "drop" : "keep")}
        data-testid="residual">{t("mixer.residual")}</button
      >
      <button class="small ghost" onclick={resetMix}
        ><Icon name="reset" size={14} />{t("mixer.reset")}</button
      >
    </div>
  {/if}
</header>

{#if !current || transport.loading}
  <div class="card muted" data-testid="mixer-loading">{t("mixer.loading")}</div>
{:else if !transport.preview}
  <div class="card error" data-testid="mixer-missing">{transport.failure}</div>
{:else}
  {#if transport.failure}<p class="error">{transport.failure}</p>{/if}
  {#if transport.memoryNote}<p class="card note" data-testid="memory-note">
      {transport.memoryNote}
    </p>{/if}

  <section class="console card">
    <div class="lane overview">
      <div class="strip">
        <span class="strip-name"><Icon name="mix" size={16} />MIX</span>
        <span class="loop-range mono" data-testid="loop-range">
          {#if transport.looping && transport.loop}<Icon
              name="loop"
              size={12}
            />{formatTime(transport.loop.start)}–{formatTime(
              transport.loop.end,
            )}{/if}
        </span>
      </div>
      <div
        class="wave"
        role="slider"
        tabindex="0"
        aria-label={t("mixer.loopHint")}
        aria-valuemin={0}
        aria-valuemax={Math.round(transport.duration)}
        aria-valuenow={Math.round(transport.position)}
        onpointerdown={pointerDown}
        onpointermove={pointerMove}
        onpointerup={pointerUp}
        data-testid="overview"
      >
        <svg viewBox="0 0 {WAVE_W} 64" preserveAspectRatio="none">
          <path d={peaksPath(transport.peaks[MIX] ?? [], WAVE_W, 64)} />
        </svg>
        {#if transport.looping && transport.loop && transport.duration}
          <div
            class="loop"
            style="left: {(transport.loop.start / transport.duration) *
              100}%; width: {((transport.loop.end - transport.loop.start) /
              transport.duration) *
              100}%"
          ></div>
        {/if}
        <div class="head" style="left: {head}%"></div>
      </div>
    </div>

    {#each stems as stem, index (stem)}
      {@const control = transport.controls[stem]}
      {@const audible = (gains[stem] ?? 0) > 0}
      {@const name = t(`stem.${stem}`)}
      <div
        class="lane"
        class:silent={!audible || transport.original}
        class:selected={transport.selected === index}
        style="--stem: {stemColor(stem)}"
        data-testid="lane-{stem}"
      >
        <button
          class="strip"
          onclick={() => selectLane(index)}
          aria-pressed={transport.selected === index}
          title="{name} ({index + 1})"
        >
          <span class="strip-name stem-ink"
            ><Icon name={stem} size={16} />{name}</span
          >
          <span class="strip-meta">
            <span class="num mono">{index + 1}</span>
            {#if transport.decoding[stem]}<span class="muted decoding"
                >{t("mixer.decoding")}</span
              >{/if}
          </span>
        </button>
        <div class="buttons">
          <button
            class="small toggle mute"
            aria-pressed={control.muted}
            title="{t('mixer.mute')} (M)"
            aria-label="{t('mixer.mute')} {name}"
            onclick={() => toggleMute(stem)}
            data-testid="mute-{stem}">M</button
          >
          <button
            class="small toggle solo"
            aria-pressed={control.soloed}
            title="{t('mixer.solo')} (S)"
            aria-label="{t('mixer.solo')} {name}"
            onclick={() => toggleSolo(stem)}
            data-testid="solo-{stem}">S</button
          >
        </div>
        <div class="pan">
          <Knob
            bind:value={control.pan}
            label="{t('mixer.pan')} {name}"
            valueText={formatPan(control.pan)}
            testid="pan-{stem}"
          />
          <span class="readout mono">{formatPan(control.pan)}</span>
        </div>
        <div class="fader">
          <input
            type="range"
            min={MIN_DB}
            max={MAX_DB}
            step="0.5"
            bind:value={control.db}
            ondblclick={() => (control.db = 0)}
            aria-label="{t('mixer.volume')} {name}"
            data-testid="volume-{stem}"
          />
          <Meter meter={transport.meters[stem]} />
        </div>
        <span class="readout mono db">{formatDb(control.db)}</span>
        <div
          class="wave"
          role="presentation"
          onpointerdown={pointerDown}
          onpointermove={pointerMove}
          onpointerup={pointerUp}
        >
          <svg viewBox="0 0 {WAVE_W} 40" preserveAspectRatio="none">
            <path d={peaksPath(transport.peaks[stem] ?? [], WAVE_W, 40)} />
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

  .tools {
    gap: 0.4rem;
  }

  .note {
    border-color: color-mix(in srgb, var(--warn) 45%, var(--border));
    color: var(--warn);
    font-size: 0.9rem;
  }

  .console {
    display: grid;
    gap: 0;
    padding: 0.4rem;
    margin-bottom: 0.9rem;
  }

  .lane {
    --stem: var(--accent);
    display: grid;
    grid-template-columns: 9.5rem auto auto 11rem 4.6rem minmax(0, 1fr);
    align-items: center;
    gap: 0.85rem;
    padding: 0.45rem 0.6rem;
    border-radius: var(--radius-sm);
  }

  .lane + .lane {
    border-top: 1px solid var(--border);
    border-top-left-radius: 0;
    border-top-right-radius: 0;
  }

  .lane.selected {
    background: var(--surface-2);
  }

  .overview {
    grid-template-columns: 9.5rem minmax(0, 1fr);
    padding-bottom: 0.6rem;
  }

  /* Scribble strip: a strip of coloured tape with the stem's name. */
  .strip {
    display: grid;
    justify-items: start;
    gap: 0.15rem;
    padding: 0.35rem 0.55rem 0.35rem 0.7rem;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--surface-2);
    box-shadow:
      inset 3px 0 0 var(--stem),
      var(--bevel);
    text-align: left;
    font: inherit;
    color: inherit;
  }

  .overview .strip {
    --stem: var(--muted);
    align-self: stretch;
    align-content: center;
  }

  button.strip {
    cursor: pointer;
  }

  .lane.selected .strip {
    border-color: color-mix(in srgb, var(--stem) 60%, var(--border));
  }

  .strip-name {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-family: var(--font-display);
    font-size: 0.78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .strip-meta {
    display: flex;
    gap: 0.4rem;
    align-items: center;
    font-size: 0.7rem;
  }

  .num {
    padding: 0 0.3rem;
    border-radius: 2px;
    background: var(--surface-3);
    color: var(--muted);
    font-size: 0.65rem;
  }

  .lane.selected .num {
    background: var(--accent);
    color: var(--accent-fg);
  }

  .decoding {
    font-size: 0.7rem;
  }

  .loop-range {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    font-size: 0.72rem;
    color: var(--accent-ink);
  }

  .buttons {
    display: flex;
    gap: 0.25rem;
  }

  .toggle {
    width: 2rem;
    padding: 0.3rem 0;
    font-family: var(--font-display);
    font-weight: 700;
  }

  .toggle.mute[aria-pressed="true"] {
    background: var(--danger);
    border-color: var(--danger);
    color: var(--danger-fg);
  }

  .toggle.solo[aria-pressed="true"] {
    background: var(--led-amber);
    border-color: var(--led-amber);
    color: #0c0b0a;
  }

  .pan {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    --knob: color-mix(in oklab, var(--stem), var(--fg) var(--stem-ink-mix));
  }

  .pan .readout {
    width: 2.2rem;
  }

  .readout {
    font-size: 0.74rem;
    color: var(--muted);
    font-variant-numeric: tabular-nums;
  }

  .db {
    text-align: right;
  }

  .fader {
    --cap: #d9d0c2;
    display: grid;
    gap: 0.35rem;
  }

  /* Console fader: a dark groove and a flat cap with a centre line. */
  input[type="range"] {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 16px;
    margin: 0;
    background: transparent;
    cursor: pointer;
  }

  input[type="range"]::-webkit-slider-runnable-track {
    height: 4px;
    border-radius: 2px;
    background: var(--well);
    box-shadow: inset 0 1px 1px rgb(0 0 0 / 60%);
  }

  input[type="range"]::-moz-range-track {
    height: 4px;
    border-radius: 2px;
    background: var(--well);
  }

  /* The cap is cream with a line in the stem colour across its middle. */
  input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 12px;
    height: 16px;
    margin-top: -6px;
    border-radius: 2px;
    border: 1px solid #000;
    background: var(--stem);
    box-shadow:
      inset 0 6px 0 var(--cap),
      inset 0 -6px 0 var(--cap),
      0 1px 2px rgb(0 0 0 / 60%);
  }

  input[type="range"]::-moz-range-thumb {
    width: 12px;
    height: 16px;
    border-radius: 2px;
    border: 1px solid #000;
    background: var(--stem);
    box-shadow:
      inset 0 6px 0 var(--cap),
      inset 0 -6px 0 var(--cap);
  }

  .wave {
    position: relative;
    cursor: pointer;
    touch-action: none;
    border-radius: 3px;
  }

  .wave svg {
    display: block;
    width: 100%;
    height: 40px;
  }

  .overview .wave {
    background: var(--well);
    padding: 4px 0;
  }

  .overview .wave svg {
    height: 64px;
  }

  .wave path {
    fill: var(--stem);
    opacity: 0.9;
    transition: opacity var(--t) ease;
  }

  .overview .wave path {
    fill: var(--lcd-fg);
    opacity: 0.55;
  }

  .lane.silent .wave path {
    opacity: 0.22;
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

  .overview .head {
    background: var(--accent);
    box-shadow: 0 0 6px var(--accent);
  }

  .loop {
    position: absolute;
    top: 0;
    bottom: 0;
    background: var(--accent-soft);
    border-inline: 1px solid var(--accent);
    pointer-events: none;
  }

  .export {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.7rem;
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

  @media (max-width: 1100px) {
    .lane {
      grid-template-columns: 8rem auto auto 9rem 4.4rem minmax(0, 1fr);
      gap: 0.6rem;
    }

    .overview {
      grid-template-columns: 8rem minmax(0, 1fr);
    }
  }
</style>
