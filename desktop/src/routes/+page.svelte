<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import {
    connectEvents,
    engineInfo,
    health,
    type EngineInfo,
  } from "$lib/engine";
  import { resolve } from "$app/paths";
  import { STEMS, stemLabel } from "$lib/stems";

  let info = $state<EngineInfo | null>(null);
  let status = $state("starting engine…");
  let heartbeats = $state(0);
  let socket: WebSocket | null = null;

  onMount(async () => {
    try {
      info = await engineInfo();
      const reply = await health(info);
      status = `engine ${reply.version} ready on port ${info.port}`;
      socket = connectEvents(info, (event) => {
        if (event.type === "heartbeat") heartbeats = event.seq;
      });
    } catch (error) {
      status = `engine error: ${error}`;
    }
  });

  onDestroy(() => socket?.close());
</script>

<main>
  <h1>Cover_Maker</h1>
  <p>Local AI stem separation for your own audio files.</p>
  <ul class="stems" aria-label="Planned stems">
    {#each STEMS as stem (stem)}
      <li>{stemLabel(stem)}</li>
    {/each}
  </ul>
  <p class="status" data-testid="engine-status">{status}</p>
  {#if info}
    <p class="status">events received: {heartbeats} · engine PID {info.pid}</p>
  {/if}
  <p><a href={resolve("/spike/audio")}>Multi-stem playback spike</a></p>
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

  a {
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
