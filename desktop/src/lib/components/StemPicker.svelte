<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { t } from "$lib/i18n.svelte";
  import { STEM_COLORS, STEMS, type Stem } from "$lib/stems";

  let { selected = $bindable<Stem[]>([]) }: { selected: Stem[] } = $props();

  function toggle(stem: Stem) {
    selected = selected.includes(stem)
      ? selected.filter((s) => s !== stem)
      : [...selected, stem];
  }
</script>

<div class="stems" role="group" aria-label={t("new.stems")}>
  {#each STEMS as stem (stem)}
    <button
      type="button"
      class="stem"
      class:on={selected.includes(stem)}
      style="--stem: {STEM_COLORS[stem]}"
      aria-pressed={selected.includes(stem)}
      onclick={() => toggle(stem)}
    >
      <span class="icon"><Icon name={stem} size={22} /></span>
      <span class="label">{t(`stem.${stem}`)}</span>
      <span class="check" aria-hidden="true"
        ><Icon name="check" size={12} strokeWidth={3} /></span
      >
    </button>
  {/each}
</div>

<style>
  .stems {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 0.6rem;
  }

  @media (max-width: 1000px) {
    .stems {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .stem {
    position: relative;
    flex-direction: column;
    gap: 0.55rem;
    padding: 0.95rem 0.6rem 0.8rem;
    border-radius: 14px;
    background: var(--surface);
    border-color: var(--border);
    color: var(--muted);
  }

  .stem:hover:not(:disabled) {
    border-color: color-mix(in srgb, var(--stem) 60%, transparent);
    color: var(--fg);
  }

  .icon {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    color: var(--stem);
    background: color-mix(in srgb, var(--stem) 12%, transparent);
    transition:
      background 0.15s ease,
      color 0.15s ease;
  }

  .label {
    font-weight: 600;
  }

  .check {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    display: grid;
    place-items: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--stem);
    color: #0a0a10;
    opacity: 0;
    transform: scale(0.6);
    transition:
      opacity 0.15s ease,
      transform 0.15s ease;
  }

  .stem.on {
    color: var(--fg);
    border-color: var(--stem);
    background: linear-gradient(
      180deg,
      color-mix(in srgb, var(--stem) 16%, var(--surface)),
      var(--surface)
    );
    box-shadow:
      0 0 0 1px var(--stem) inset,
      0 8px 24px color-mix(in srgb, var(--stem) 22%, transparent);
  }

  .stem.on .icon {
    background: var(--stem);
    color: #0a0a10;
  }

  .stem.on .check {
    opacity: 1;
    transform: scale(1);
  }
</style>
