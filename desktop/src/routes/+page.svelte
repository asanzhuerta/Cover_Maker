<script lang="ts">
  import { STEMS, stemLabel } from "$lib/stems";
</script>

<main>
  <h1>Cover_Maker</h1>
  <p>Local AI stem separation for your own audio files.</p>
  <ul class="stems" aria-label="Planned stems">
    {#each STEMS as stem (stem)}
      <li>{stemLabel(stem)}</li>
    {/each}
  </ul>
  <p class="status">v2 is under construction.</p>
</main>

<style>
  :global(:root) {
    --bg: #f7f7f9;
    --fg: #17171c;
    --muted: #5d5d6b;
    --accent: #6b4eff;
    --chip: #ebe8ff;
    color-scheme: light dark;
    font-family: system-ui, "Segoe UI", sans-serif;
  }

  @media (prefers-color-scheme: dark) {
    :global(:root) {
      --bg: #121218;
      --fg: #ececf2;
      --muted: #a1a1b2;
      --chip: #2a2550;
    }
  }

  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--fg);
  }

  main {
    display: grid;
    place-content: center;
    gap: 0.75rem;
    min-height: 100vh;
    text-align: center;
  }

  h1 {
    margin: 0;
    color: var(--accent);
  }

  .stems {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.5rem;
    padding: 0;
    list-style: none;
  }

  .stems li {
    padding: 0.35rem 0.9rem;
    border-radius: 999px;
    background: var(--chip);
  }

  .status {
    color: var(--muted);
  }
</style>
