<script lang="ts">
  import { ICONS, type IconName, type IconShape } from "$lib/icons";

  let {
    name,
    size = 18,
    strokeWidth = 1.8,
  }: { name: IconName; size?: number; strokeWidth?: number } = $props();

  const shape: IconShape = $derived(ICONS[name]);
</script>

<svg
  class="icon"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width={strokeWidth}
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#each shape.stroke as d (d)}<path {d} />{/each}
  {#each shape.fill ?? [] as d (d)}<path
      {d}
      fill="currentColor"
      stroke="none"
    />{/each}
</svg>

<style>
  .icon {
    flex: none;
    display: block;
  }
</style>
