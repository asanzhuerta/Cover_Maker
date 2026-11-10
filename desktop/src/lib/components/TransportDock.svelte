<script lang="ts">
  // Bottom transport: stays on every page, so the song keeps playing while
  // the user looks at the queue, the library or the settings.
  import { resolve } from "$app/paths";
  import Icon from "$lib/components/Icon.svelte";
  import Lcd from "$lib/components/Lcd.svelte";
  import Meter from "$lib/components/Meter.svelte";
  import { t } from "$lib/i18n.svelte";
  import { formatTime, peaksPath } from "$lib/mixer";
  import {
    MIX,
    seek,
    toggle,
    toggleLoop,
    transport,
  } from "$lib/transport.svelte";

  const WAVE_W = 600;

  const loaded = $derived(transport.duration > 0);
  const head = $derived(
    loaded ? (transport.position / transport.duration) * 100 : 0,
  );
  const wave = $derived(peaksPath(transport.peaks[MIX] ?? [], WAVE_W, 24));

  function scrub(event: PointerEvent) {
    const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const share = Math.min(
      1,
      Math.max(0, (event.clientX - box.left) / box.width),
    );
    seek(share * transport.duration);
  }
</script>

<section class="dock" aria-label={t("dock.label")} data-testid="dock">
  <div class="buttons">
    <button
      class="primary play"
      disabled={!loaded}
      onclick={() => void toggle()}
      aria-label={transport.playing ? t("mixer.pause") : t("mixer.play")}
      data-testid="play"
      ><Icon name={transport.playing ? "pause" : "play"} size={20} /></button
    >
    <button
      class="small led-button"
      disabled={!loaded}
      aria-pressed={transport.looping}
      onclick={toggleLoop}
      title="{t('mixer.loop')} (L)"
      data-testid="loop"><Icon name="loop" size={14} /></button
    >
    <div class="ab" role="group" aria-label={t("mixer.abHint")}>
      <button
        class="small led-button"
        disabled={!loaded}
        aria-pressed={transport.original}
        onclick={() => (transport.original = true)}
        title="{t('mixer.original')} (A)"
        data-testid="ab-original">A</button
      >
      <button
        class="small led-button"
        disabled={!loaded}
        aria-pressed={!transport.original}
        onclick={() => (transport.original = false)}
        title="{t('mixer.custom')} (A)"
        data-testid="ab-custom">B</button
      >
    </div>
  </div>

  <div class="song">
    {#if loaded && transport.itemId !== null}
      <a
        class="title"
        href={resolve("/mixer/[item]", { item: String(transport.itemId) })}
        title={t("dock.open")}>{transport.preview?.title || t("mixer.title")}</a
      >
      <div
        class="scrub"
        role="slider"
        tabindex="-1"
        aria-label={t("mixer.loopHint")}
        aria-valuemin={0}
        aria-valuemax={Math.round(transport.duration)}
        aria-valuenow={Math.round(transport.position)}
        aria-valuetext="{formatTime(transport.position)} / {formatTime(
          transport.duration,
        )}"
        onpointerdown={scrub}
      >
        <svg viewBox="0 0 {WAVE_W} 24" preserveAspectRatio="none">
          <path d={wave} class="rest" />
        </svg>
        <svg
          viewBox="0 0 {WAVE_W} 24"
          preserveAspectRatio="none"
          class="played"
          style="clip-path: inset(0 {100 - head}% 0 0)"
        >
          <path d={wave} />
        </svg>
        <div class="head" style="left: {head}%"></div>
      </div>
    {:else if transport.loading}
      <span class="muted">{t("mixer.loading")}</span>
    {:else}
      <span class="muted empty">{t("dock.empty")}</span>
    {/if}
  </div>

  <div class="output" title={t("mixer.output")}>
    <span class="caps">L</span>
    <Meter meter={transport.meters.L} segments={20} />
    <span class="caps">R</span>
    <Meter meter={transport.meters.R} segments={20} />
  </div>

  <Lcd />
</section>

<style>
  .dock {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 5;
    height: var(--dock);
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) 150px auto;
    align-items: center;
    gap: 1.1rem;
    padding: 0 0.9rem 0 0.9rem;
    background: var(--surface);
    border-top: 1px solid var(--border-strong);
    box-shadow: 0 -8px 24px rgb(0 0 0 / 18%);
  }

  .buttons {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .play {
    width: 46px;
    height: 46px;
    padding: 0;
    border-radius: 50%;
  }

  .ab {
    display: inline-flex;
  }

  .ab button:first-child {
    border-radius: var(--radius-sm) 0 0 var(--radius-sm);
  }

  .ab button:last-child {
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    margin-left: -1px;
  }

  .song {
    display: grid;
    gap: 0.25rem;
    min-width: 0;
  }

  .title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--fg);
    font-weight: 600;
    text-decoration: none;
  }

  .title:hover {
    text-decoration: underline;
  }

  .empty {
    font-size: 0.88rem;
  }

  .scrub {
    position: relative;
    height: 24px;
    cursor: pointer;
  }

  .scrub svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .scrub path {
    fill: var(--accent);
  }

  .scrub .rest {
    fill: color-mix(in srgb, var(--fg) 24%, transparent);
  }

  .head {
    position: absolute;
    top: -2px;
    bottom: -2px;
    width: 2px;
    margin-left: -1px;
    background: var(--fg);
    pointer-events: none;
  }

  .output {
    display: grid;
    grid-template-columns: auto 1fr;
    align-items: center;
    gap: 0.3rem 0.45rem;
  }

  .output .caps {
    font-size: 0.6rem;
  }

  @media (max-width: 1000px) {
    .output {
      display: none;
    }

    .dock {
      grid-template-columns: auto minmax(0, 1fr) auto;
    }
  }
</style>
