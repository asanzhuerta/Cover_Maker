<script lang="ts" module>
  export type LogoVariant = "reel" | "fader" | "cursor";
</script>

<script lang="ts">
  let {
    variant = "reel",
    size = 32,
    blink = false,
  }: {
    variant?: LogoVariant;
    size?: number;
    /** Blink the underscore like a cursor (off with reduced motion). */
    blink?: boolean;
  } = $props();
</script>

<!-- Cream parts follow the text colour; the underscore is signal orange. -->
<svg
  class="logo"
  class:blink
  width={size}
  height={size}
  viewBox="0 0 64 64"
  aria-hidden="true"
>
  {#if variant === "reel"}
    <!-- Flange open into a C, the wound tape inside, the tape leaving through the gap. -->
    <path class="accent" d="M27 37.5H59" stroke-width="5" fill="none" />
    <path
      d="M41.56 16.79A19 19 0 1 0 41.56 41.21"
      fill="none"
      stroke="currentColor"
      stroke-width="5"
    />
    <path
      fill="currentColor"
      fill-rule="evenodd"
      d="M16 29a11 11 0 1 0 22 0a11 11 0 1 0-22 0ZM23.8 29a3.2 3.2 0 1 0 6.4 0a3.2 3.2 0 1 0-6.4 0Z"
    />
  {:else if variant === "fader"}
    <path
      d="M6 32h8M8 12h6M8 22h6M8 42h6M8 52h6M50 12h6M50 22h6M50 32h8M50 42h6M50 52h6"
      stroke="currentColor"
      stroke-opacity="0.5"
      stroke-width="2.5"
      stroke-linecap="round"
    />
    <rect x="29" y="6" width="6" height="52" rx="3" class="groove" />
    <rect x="18" y="34" width="28" height="16" rx="3" fill="currentColor" />
    <rect x="18" y="40.5" width="28" height="3" class="accent-fill" />
  {:else}
    <path
      d="M36.89 20.3A16 16 0 1 0 36.89 41.7"
      fill="none"
      stroke="currentColor"
      stroke-width="9"
    />
    <rect x="40" y="44.5" width="18" height="7" class="accent-fill cursor" />
  {/if}
</svg>

<style>
  .logo {
    flex: none;
    display: block;
  }

  .accent {
    stroke: var(--accent, #ff6a3d);
  }

  .accent-fill {
    fill: var(--accent, #ff6a3d);
  }

  .groove {
    fill: currentColor;
    fill-opacity: 0.25;
  }

  .blink .cursor,
  .blink .accent {
    animation: blink 1.1s steps(1) infinite;
  }

  @keyframes blink {
    50% {
      opacity: 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .blink .cursor,
    .blink .accent {
      animation: none;
    }
  }
</style>
