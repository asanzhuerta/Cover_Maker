<script lang="ts">
  import { t } from "$lib/i18n.svelte";
  import { STEMS, type Stem } from "$lib/stems";

  let { selected = $bindable<Stem[]>([]) }: { selected: Stem[] } = $props();

  function toggle(stem: Stem) {
    selected = selected.includes(stem)
      ? selected.filter((s) => s !== stem)
      : [...selected, stem];
  }
</script>

<div class="chips" role="group" aria-label={t("new.stems")}>
  {#each STEMS as stem (stem)}
    <button
      type="button"
      class="chip"
      class:on={selected.includes(stem)}
      aria-pressed={selected.includes(stem)}
      onclick={() => toggle(stem)}
    >
      {t(`stem.${stem}`)}
    </button>
  {/each}
</div>

<style>
  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .chip {
    border-radius: 999px;
    padding: 0.4rem 1rem;
  }

  .chip.on {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-fg);
    font-weight: 600;
  }
</style>
