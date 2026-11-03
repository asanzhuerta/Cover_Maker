<script lang="ts">
  import { waveBars } from "$lib/wave";

  let {
    seed,
    bars = 48,
    height = 32,
    progress = 1,
    color = "var(--accent)",
    live = false,
  }: {
    seed: string;
    bars?: number;
    height?: number;
    /** Share of bars drawn in `color` (0–1); the rest are dimmed. */
    progress?: number;
    color?: string;
    /** Animate the bars around the progress head (work in progress). */
    live?: boolean;
  } = $props();

  const shape = $derived(waveBars(seed, bars));
  const head = $derived(Math.round(progress * bars));
</script>

<svg
  class="wave"
  class:live
  viewBox="0 0 {bars * 4} {height}"
  preserveAspectRatio="none"
  style="height: {height}px; --wave: {color}"
  aria-hidden="true"
>
  {#each shape as level, i (i)}
    {@const h = Math.max(2, level * height)}
    <rect
      x={i * 4 + 0.5}
      y={(height - h) / 2}
      width="2.6"
      height={h}
      rx="1.3"
      class:on={i < head}
      class:head={live && Math.abs(i - head) < 3}
      style="animation-delay: {(i % 6) * 90}ms"
    />
  {/each}
</svg>

<style>
  .wave {
    display: block;
    width: 100%;
  }

  rect {
    fill: var(--wave-off, var(--surface-3));
    transition: fill 0.4s ease;
  }

  rect.on {
    fill: var(--wave);
  }

  .live rect.head {
    fill: var(--wave);
    transform-box: fill-box;
    transform-origin: center;
    animation: pulse 0.9s ease-in-out infinite alternate;
  }

  @keyframes pulse {
    from {
      transform: scaleY(0.45);
    }
    to {
      transform: scaleY(1.1);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .live rect.head {
      animation: none;
    }
  }
</style>
