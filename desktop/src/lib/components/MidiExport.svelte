<script lang="ts">
  import { errorMessage, type Schemas } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import { connection, isTauri, onEvent } from "$lib/connection.svelte";
  import { t } from "$lib/i18n.svelte";
  import {
    midiProgress,
    overallFraction,
    toggleStem,
    type MidiProgress,
  } from "$lib/midi";
  import type { Stem } from "$lib/stems";

  let { itemId, stems }: { itemId: number; stems: Stem[] } = $props();

  let chosen = $state<Stem[]>([]);
  let converting = $state(false);
  let progress = $state<MidiProgress | null>(null);
  let result = $state<Schemas["MidiOut"] | null>(null);
  let failure = $state("");

  const share = $derived(progress ? overallFraction(progress) : 0);

  $effect(() =>
    onEvent((event) => {
      const update = midiProgress(event, itemId);
      if (update && converting) progress = update;
    }),
  );

  function stemName(stem: string): string {
    return (stems as string[]).includes(stem)
      ? t(`stem.${stem as Stem}`)
      : stem;
  }

  async function convert() {
    if (!connection.api || chosen.length === 0) return;
    converting = true;
    progress = null;
    result = null;
    failure = "";
    const { data, error } = await connection.api.POST("/items/{item_id}/midi", {
      params: { path: { item_id: itemId } },
      body: { stems: chosen },
    });
    converting = false;
    progress = null;
    if (data) result = data;
    else failure = errorMessage(error);
  }

  async function reveal(path: string) {
    const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
    await revealItemInDir(path);
  }
</script>

<section class="card midi" aria-labelledby="midi-title" data-testid="midi">
  <header class="row head">
    <h2 id="midi-title">{t("midi.title")}</h2>
    <span class="muted small-text">{t("midi.hint")}</span>
  </header>

  <div class="row stems" role="group" aria-label={t("midi.stems")}>
    {#each stems as stem (stem)}
      <label class="check">
        <input
          type="checkbox"
          checked={chosen.includes(stem)}
          disabled={converting}
          onchange={() => (chosen = toggleStem(chosen, stem, stems))}
          data-testid="midi-{stem}"
        />{stemName(stem)}
      </label>
    {/each}
    <button
      class="primary"
      onclick={convert}
      disabled={converting || chosen.length === 0}
      data-testid="midi-export"
      ><Icon name="download" size={16} />{converting
        ? t("midi.converting")
        : t("midi.export")}</button
    >
  </div>

  {#if converting}
    <div
      class="progress"
      role="progressbar"
      aria-label={t("midi.converting")}
      aria-valuemin="0"
      aria-valuemax="100"
      aria-valuenow={Math.round(share * 100)}
      data-testid="midi-progress"
    >
      <span class="label"
        >{progress
          ? t("midi.step")
              .replace("{stem}", stemName(progress.stem))
              .replace("{n}", String(progress.index + 1))
              .replace("{total}", String(progress.total))
          : t("midi.converting")}
        {Math.round(share * 100)}%</span
      >
      <span class="track"
        ><span class="fill" style:width="{Math.max(2, share * 100)}%"
        ></span></span
      >
    </div>
  {/if}

  {#if result}
    <div class="saved" data-testid="midi-saved">
      <span class="muted">{t("midi.saved")}</span>
      <ul>
        {#each result.files as file (file.stem)}
          <li>
            <code>{file.path}</code>
            {#if file.notes === 0}<span class="badge warn"
                >{t("midi.noNotes")}</span
              >{/if}
          </li>
        {/each}
      </ul>
      {#if !result.tempo_from_analysis}
        <p class="muted small-text">{t("midi.noTempo")}</p>
      {/if}
      {#if isTauri() && result.files.length}
        <button class="small" onclick={() => reveal(result!.files[0].path)}
          ><Icon name="folder" size={14} />{t("queue.open")}</button
        >
      {/if}
    </div>
  {/if}
  {#if failure}<p class="error">{failure}</p>{/if}
</section>

<style>
  .midi {
    display: grid;
    gap: 0.7rem;
  }

  .head {
    align-items: baseline;
    gap: 0.8rem;
  }

  .head h2 {
    margin: 0;
  }

  .stems {
    flex-wrap: wrap;
    align-items: center;
    gap: 0.7rem;
  }

  .check {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.88rem;
  }

  .progress {
    display: grid;
    gap: 0.3rem;
    max-width: 360px;
  }

  .progress .label {
    font-size: 0.78rem;
    color: var(--ok);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .progress .track {
    height: 6px;
    border-radius: 2px;
    background: var(--well);
    overflow: hidden;
  }

  .progress .fill {
    display: block;
    height: 100%;
    background: var(--ok);
  }

  .saved {
    display: grid;
    gap: 0.4rem;
    justify-items: start;
    font-size: 0.88rem;
  }

  .saved ul {
    margin: 0;
    padding-left: 1.1rem;
  }

  code {
    overflow-wrap: anywhere;
  }
</style>
