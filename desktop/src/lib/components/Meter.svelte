<script lang="ts">
  import { meterShare, silentMeter, type MeterState } from "$lib/meter";

  let {
    meter = silentMeter(),
    segments = 24,
  }: { meter?: MeterState; segments?: number } = $props();

  // LEDs light whole segments: snap the reading to the segment grid.
  const lit = $derived(Math.round(meterShare(meter.db) * segments) / segments);
  const peak = $derived(
    Math.ceil(meterShare(meter.peak) * segments) / segments,
  );
  const peakColor = $derived(
    meter.peak > -3
      ? "var(--led-red)"
      : meter.peak > -12
        ? "var(--led-amber)"
        : "var(--led-green)",
  );
</script>

<!-- Visual feedback only: the numbers are in the faders' readouts. -->
<div
  class="meter"
  style="--lit: {lit}; --peak: {peak}; --segments: {segments}; --peak-color: {peakColor}"
  aria-hidden="true"
>
  <div class="lit"></div>
  {#if peak > 0}<div class="peak"></div>{/if}
</div>

<style>
  /* Green to −12 dBFS, amber to −3, red above (scale −48…0 dBFS). */
  .meter {
    --scale: linear-gradient(
      to right,
      var(--led-green) 0 75%,
      var(--led-amber) 75% 93.75%,
      var(--led-red) 93.75%
    );
    --cells: repeating-linear-gradient(
      to right,
      #000 0 calc(100% / var(--segments) - 2px),
      transparent calc(100% / var(--segments) - 2px)
        calc(100% / var(--segments))
    );
    position: relative;
    height: 8px;
    min-width: 60px;
    padding: 2px;
    border-radius: 2px;
    background: var(--well);
    box-shadow: inset 0 1px 2px rgb(0 0 0 / 60%);
  }

  .meter::before,
  .lit {
    content: "";
    position: absolute;
    inset: 2px;
    background: var(--scale);
    -webkit-mask: var(--cells);
    mask: var(--cells);
  }

  .meter::before {
    opacity: 0.14;
  }

  /* Never transitioned: the ballistics are computed, not eased. */
  .lit {
    clip-path: inset(0 calc((1 - var(--lit)) * 100%) 0 0);
  }

  .peak {
    position: absolute;
    top: 2px;
    bottom: 2px;
    left: calc(
      2px + (100% - 4px) * var(--peak) - (100% - 4px) / var(--segments)
    );
    width: calc((100% - 4px) / var(--segments) - 2px);
    background: var(--peak-color);
  }
</style>
