<script lang="ts">
  import Icon from "$lib/components/Icon.svelte";
  import { t } from "$lib/i18n.svelte";
  import { CHOOSABLE, STEM_COLORS, type Stem } from "$lib/stems";

  let { selected = $bindable<Stem[]>([]) }: { selected: Stem[] } = $props();

  function toggle(stem: Stem) {
    selected = selected.includes(stem)
      ? selected.filter((s) => s !== stem)
      : [...selected, stem];
  }
</script>

<div class="stems" role="group" aria-label={t("new.stems")}>
  {#each CHOOSABLE as stem (stem)}
    <button
      type="button"
      class="stem"
      class:sub={stem.includes(".")}
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
<p class="parts muted">{t("new.stems.parts")}</p>

<style>
  .stems {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 0.6rem;
  }

  @media (max-width: 1200px) {
    .stems {
      grid-template-columns: repeat(4, 1fr);
    }
  }

  @media (max-width: 640px) {
    .stems {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  .parts {
    margin: 0.6rem 0 0;
    font-size: 0.8rem;
  }

  /* A channel button: coloured tape on top, an LED that lights when chosen. */
  .stem {
    position: relative;
    flex-direction: column;
    gap: 0.55rem;
    padding: 1rem 0.6rem 0.8rem;
    border-radius: var(--radius);
    background: var(--surface);
    border-color: var(--border);
    color: var(--muted);
    box-shadow:
      inset 0 3px 0 color-mix(in srgb, var(--stem) 35%, transparent),
      var(--bevel);
  }

  /* A part of another stem: a split tape on top. */
  .stem.sub {
    box-shadow:
      inset 0 3px 0 color-mix(in srgb, var(--stem) 35%, transparent),
      inset 0 -1px 0 color-mix(in srgb, var(--stem) 20%, transparent),
      var(--bevel);
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
    border-radius: 50%;
    color: color-mix(in oklab, var(--stem), var(--fg) var(--stem-ink-mix));
    background: var(--surface-2);
    border: 1px solid var(--border);
    transition:
      background var(--t) ease,
      color var(--t) ease;
  }

  .label {
    text-align: center;
    line-height: 1.25;
    font-family: var(--font-display);
    font-size: 0.8rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .check {
    position: absolute;
    top: 0.55rem;
    right: 0.55rem;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--surface-3);
    box-shadow: inset 0 1px 1px rgb(0 0 0 / 40%);
    transition:
      background var(--t) ease,
      box-shadow var(--t) ease;
  }

  .check :global(svg) {
    display: none;
  }

  .stem.on {
    color: var(--fg);
    border-color: var(--stem);
    background: var(--surface-2);
    box-shadow:
      inset 0 3px 0 var(--stem),
      var(--bevel);
  }

  .stem.on .icon {
    background: var(--stem);
    border-color: transparent;
    color: #0c0b0a;
  }

  .stem.on .check {
    background: var(--stem);
    box-shadow: 0 0 6px var(--stem);
  }
</style>
