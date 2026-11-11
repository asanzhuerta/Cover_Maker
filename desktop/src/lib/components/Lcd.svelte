<script lang="ts">
  // Amber-on-black display: engine and runtime lights, the clock, and the
  // song's tempo, key and tuning as played (after the practice settings).
  // While the speed trainer runs, a TRAIN cell shows the tempo and passes.
  import { bootstrap, separationReady } from "$lib/bootstrap.svelte";
  import { connection } from "$lib/connection.svelte";
  import { t } from "$lib/i18n.svelte";
  import { formatClock } from "$lib/mixer";
  import {
    foldCents,
    formatCents,
    formatShift,
    formatTempo,
    shiftedKey,
  } from "$lib/practice";
  import { transport } from "$lib/transport.svelte";

  const engineLed = $derived(
    connection.status === "ready"
      ? "on"
      : connection.status === "starting"
        ? "blink"
        : "fault",
  );
  const engineText = $derived(
    connection.status === "ready"
      ? t("engine.ready")
      : connection.status === "starting"
        ? t("engine.starting")
        : t("engine.offline"),
  );

  const phase = $derived(bootstrap.status.separation);
  const runtimeLed = $derived(
    separationReady(bootstrap.status)
      ? "on"
      : phase.state === "running"
        ? "blink"
        : phase.state === "failed"
          ? "fault"
          : "off",
  );
  const runtimeText = $derived(
    separationReady(bootstrap.status)
      ? t("bootstrap.separationReady")
      : phase.state === "running"
        ? t("bootstrap.separation")
        : phase.state === "failed"
          ? t("bootstrap.separationFailed")
          : t("lcd.runtimeMissing"),
  );
  const torch = $derived(
    bootstrap.status.torch ? ` (${bootstrap.status.torch})` : "",
  );

  const loaded = $derived(transport.duration > 0);
  const analysis = $derived(loaded ? transport.analysis : null);
  const practice = $derived(transport.practice);
  const bpm = $derived(
    analysis && analysis.bpm > 0
      ? (analysis.bpm * practice.tempo).toFixed(0)
      : "",
  );
  const key = $derived(
    analysis && analysis.key_confidence > 0
      ? shiftedKey(analysis.key, analysis.mode, practice.semitones)
      : "",
  );
  const tune = $derived(
    analysis
      ? formatCents(foldCents(analysis.tuning_cents + practice.cents))
      : "",
  );
  const bpmHint = $derived(
    analysis
      ? t("lcd.bpmHint")
          .replace("{bpm}", analysis.bpm.toFixed(1))
          .replace("{tempo}", formatTempo(practice.tempo))
      : t("lcd.soon"),
  );
  const keyHint = $derived(
    analysis
      ? t("lcd.keyHint")
          .replace("{key}", shiftedKey(analysis.key, analysis.mode, 0))
          .replace("{shift}", formatShift(practice.semitones, practice.cents))
      : t("lcd.soon"),
  );
</script>

<div class="lcd" role="group" aria-label={t("lcd.label")}>
  <div class="lights">
    <span
      class="light"
      data-testid="engine-status"
      data-state={connection.status}
      role="status"
      aria-live="polite"
      title={connection.error || engineText}
      ><span class="led {engineLed}"></span>{t("lcd.engine")}<span
        class="sr-only">: {engineText}</span
      ></span
    >
    <span
      class="light"
      data-testid="runtime-light"
      data-state={runtimeLed}
      title={phase.state === "failed" ? phase.error : runtimeText + torch}
      ><span class="led {runtimeLed}"></span>{t("lcd.runtime")}<span
        class="sr-only">: {runtimeText}</span
      ></span
    >
    {#if connection.demo}<span class="demo">{t("lcd.demo")}</span>{/if}
  </div>
  <div class="cell clock" data-testid="time">
    <span class="tag">POS</span>
    <!-- Unlit segments show through, as on a real display. -->
    <span class="digits"
      ><span class="ghost" aria-hidden="true">88:88.8</span><span class="value"
        >{loaded ? formatClock(transport.position) : ""}</span
      ></span
    >
    {#if loaded}<span class="total">/ {formatClock(transport.duration)}</span
      >{/if}
  </div>
  <div class="cell" class:slot={!bpm} title={bpmHint} data-testid="lcd-bpm">
    <span class="tag"
      >{t("lcd.bpm")}{#if practice.tempo !== 1}
        {formatTempo(practice.tempo)}{/if}</span
    >
    <span class="digits">{bpm || "---"}</span>
  </div>
  <div class="cell" class:slot={!key} title={keyHint} data-testid="lcd-key">
    <span class="tag">{t("lcd.key")}</span>
    <span class="digits">{key || "--"}</span>
  </div>
  <div
    class="cell"
    class:slot={!tune}
    title={analysis ? t("lcd.tuneHint") : t("lcd.soon")}
    data-testid="lcd-tune"
  >
    <span class="tag">{t("lcd.tuning")}</span>
    <span class="digits">{tune || "---"}</span>
  </div>
  {#if loaded && transport.trainer.on}
    <div class="cell" data-testid="lcd-train" role="status">
      <span class="tag">{t("lcd.train")} ×{transport.passes}</span>
      <span class="digits">{formatTempo(practice.tempo)}</span>
    </div>
  {/if}
</div>

<style>
  .lcd {
    display: flex;
    align-items: stretch;
    gap: 0;
    height: 52px;
    padding: 0 0.3rem;
    border-radius: 6px;
    background: var(--lcd-bg);
    border: 1px solid #000;
    box-shadow:
      inset 0 2px 8px rgb(0 0 0 / 80%),
      0 1px 0 rgb(255 255 255 / 6%);
    color: var(--lcd-fg);
    font-family: var(--font-mono);
    text-shadow: 0 0 6px rgb(255 179 64 / 35%);
    white-space: nowrap;
  }

  .lights,
  .cell {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 0 0.7rem;
  }

  .cell + .cell,
  .lights + .cell {
    border-left: 1px solid var(--lcd-dim);
  }

  .lights {
    gap: 0.15rem;
    font-size: 0.66rem;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }

  .light {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }

  .led {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #2a2117;
    box-shadow: inset 0 1px 1px rgb(0 0 0 / 70%);
  }

  .led.on {
    background: var(--led-green);
    box-shadow: 0 0 6px var(--led-green);
  }

  .led.blink {
    background: var(--led-amber);
    box-shadow: 0 0 6px var(--led-amber);
    animation: led-blink 1s steps(1) infinite;
  }

  .led.fault {
    background: var(--led-red);
    box-shadow: 0 0 6px var(--led-red);
  }

  @keyframes led-blink {
    50% {
      opacity: 0.25;
    }
  }

  .demo {
    font-size: 0.6rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    padding: 0 0.3rem;
    border: 1px solid var(--lcd-fg);
    border-radius: 2px;
    align-self: flex-start;
  }

  .tag {
    font-size: 0.6rem;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    opacity: 0.7;
  }

  .digits {
    position: relative;
    font-size: 1.15rem;
    font-weight: 500;
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
  }

  .ghost {
    color: var(--lcd-dim);
    text-shadow: none;
  }

  .value {
    position: absolute;
    inset: 0;
  }

  .clock {
    flex-direction: row;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
    align-content: center;
    row-gap: 0;
  }

  .clock .tag {
    flex-basis: 100%;
  }

  .total {
    font-size: 0.78rem;
    opacity: 0.75;
  }

  .slot .digits {
    opacity: 0.6;
  }

  @media (prefers-reduced-motion: reduce) {
    .led.blink {
      animation: none;
    }
  }
</style>
