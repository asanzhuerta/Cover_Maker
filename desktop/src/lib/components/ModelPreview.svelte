<script lang="ts">
  // Illustrative mock of the Models page for the welcome tutorial: fixed
  // example cards, not the catalogue (the real list needs the engine to have
  // scanned the PC and the separation runtime to be installed).
  import Icon from "$lib/components/Icon.svelte";
  import { t } from "$lib/i18n.svelte";
  import { STEM_COLORS, type Stem } from "$lib/stems";

  const cards: { stems: Stem[]; recommended: boolean; progress?: number }[] = [
    {
      stems: ["vocals", "guitar", "drums", "bass", "piano", "other"],
      recommended: true,
      progress: 0.62,
    },
    { stems: ["vocals", "drums", "bass", "other"], recommended: false },
  ];
</script>

<figure class="preview" aria-label={t("tour.previewLabel")}>
  <span class="badge accent tag">{t("tour.preview")}</span>
  {#each cards as card, i (i)}
    <div class="card mock" class:recommended={card.recommended}>
      <div class="head">
        <span class="line name"></span>
        {#if card.recommended}
          <span class="badge accent">{t("models.recommended")}</span>
        {/if}
      </div>
      <div class="stems">
        {#each card.stems as stem (stem)}
          <span class="stem" style="--stem: {STEM_COLORS[stem]}"
            ><Icon name={stem} size={13} /></span
          >
        {/each}
      </div>
      <span class="line short"></span>
      {#if card.progress !== undefined}
        <div class="download">
          <span class="label"
            >{t("models.installing")} {Math.round(card.progress * 100)}%</span
          >
          <span class="track"
            ><span class="fill" style:width="{card.progress * 100}%"
            ></span></span
          >
        </div>
      {:else}
        <span class="fake-button"
          ><Icon name="shield" size={13} />{t("models.install")}</span
        >
      {/if}
    </div>
  {/each}
  <figcaption class="muted">{t("tour.previewCaption")}</figcaption>
</figure>

<style>
  .preview {
    position: relative;
    margin: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 0.8rem;
    padding: 1rem;
    border: 1px dashed var(--border-strong);
    border-radius: var(--radius);
    pointer-events: none;
    user-select: none;
  }

  .tag {
    position: absolute;
    top: -0.7rem;
    left: 1rem;
  }

  .mock {
    display: grid;
    gap: 0.6rem;
    opacity: 0.85;
  }

  .mock.recommended {
    box-shadow: 0 0 0 1px var(--accent-soft);
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .line {
    display: block;
    height: 10px;
    border-radius: 5px;
    background: var(--border-strong);
  }

  .line.name {
    width: 55%;
    height: 12px;
  }

  .line.short {
    width: 35%;
    background: var(--border);
  }

  .stems {
    display: flex;
    gap: 0.3rem;
  }

  .stem {
    display: grid;
    place-items: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    color: color-mix(in oklab, var(--stem), var(--fg) var(--stem-ink-mix));
    background: color-mix(in srgb, var(--stem) 16%, transparent);
  }

  .fake-button {
    justify-self: start;
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.3rem 0.7rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-strong);
    font-size: 0.8rem;
  }

  .download {
    display: grid;
    gap: 0.3rem;
  }

  .download .label {
    font-size: 0.78rem;
    color: var(--ok);
    font-weight: 600;
  }

  .download .track {
    height: 6px;
    border-radius: 2px;
    background: var(--well);
    overflow: hidden;
  }

  .download .fill {
    display: block;
    height: 100%;
    background: var(--ok);
  }

  figcaption {
    grid-column: 1 / -1;
    font-size: 0.82rem;
  }
</style>
