<script lang="ts">
  // The Cover_Maker mark (ADR-009): a tape reel whose flange opens into a C,
  // with the tape leaving through the gap as the underscore of the name.
  let { size = 32 }: { size?: number } = $props();
</script>

<!-- Cream parts follow the text colour; the tape is signal orange. -->
<svg
  class="logo"
  width={size}
  height={size}
  viewBox="0 0 64 64"
  aria-hidden="true"
>
  <path class="tape" d="M27 37.5H59" stroke-width="5" fill="none" />
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
</svg>

<style>
  .logo {
    flex: none;
    display: block;
  }

  .tape {
    stroke: var(--accent, #ff6a3d);
  }
</style>
