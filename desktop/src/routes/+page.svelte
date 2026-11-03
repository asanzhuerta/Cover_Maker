<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import StemPicker from "$lib/components/StemPicker.svelte";
  import { connection, isTauri } from "$lib/connection.svelte";
  import { t } from "$lib/i18n.svelte";
  import { displayName } from "$lib/jobs";
  import { settings } from "$lib/settings.svelte";
  import type { Stem } from "$lib/stems";

  const AUDIO = [
    "wav",
    "flac",
    "mp3",
    "m4a",
    "aac",
    "ogg",
    "opus",
    "webm",
    "aiff",
    "aif",
    "wma",
  ];

  let inputs = $state<string[]>([]);
  let link = $state("");
  let stems = $state<Stem[]>(["vocals"]);
  let mode = $state<"extract" | "without">("extract");
  let keepResidual = $state(true);
  let preset = $state<"auto" | "fast" | "balanced" | "max">("auto");
  let outputDir = $state(settings.outputDir);
  let format = $state(settings.format);
  let rights = $state(false);
  let dragging = $state(false);
  let error = $state("");
  let missing = $state<string[]>([]);
  let busy = $state(false);
  let unlisten: (() => void) | null = null;

  const hasLinks = $derived(inputs.some((i) => /^https?:\/\//i.test(i)));
  const canStart = $derived(
    connection.status === "ready" &&
      inputs.length > 0 &&
      stems.length > 0 &&
      outputDir.trim() !== "" &&
      (!hasLinks || rights) &&
      !busy,
  );

  function add(paths: string[]) {
    inputs = [...new Set([...inputs, ...paths])];
  }

  function addLink() {
    const value = link.trim();
    if (!value) return;
    add([value]);
    link = "";
  }

  async function pickFiles() {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const chosen = await open({
      multiple: true,
      filters: [{ name: "Audio", extensions: AUDIO }],
    });
    if (chosen) add(Array.isArray(chosen) ? chosen : [chosen]);
  }

  async function pickFolder(target: "input" | "output") {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const chosen = await open({ directory: true });
    if (typeof chosen !== "string") return;
    if (target === "input") add([chosen]);
    else outputDir = chosen;
  }

  async function start() {
    if (!connection.api) return;
    busy = true;
    error = "";
    missing = [];
    const { data, error: problem } = await connection.api.POST("/jobs", {
      body: {
        inputs,
        stems,
        mode,
        residual: keepResidual ? "keep" : "drop",
        preset,
        output_dir: outputDir,
        output_format: format,
        allow_cpu_fallback: settings.allowCpu,
        rights_confirmed: rights,
      },
    });
    busy = false;
    if (data) {
      inputs = [];
      rights = false;
      void goto(resolve("/queue"));
      return;
    }
    const body = problem as
      { detail?: unknown; code?: string; models?: string[] } | undefined;
    if (body?.code === "model_not_installed") missing = body.models ?? [];
    error =
      typeof body?.detail === "string" ? body.detail : JSON.stringify(problem);
  }

  onMount(async () => {
    if (!isTauri()) return;
    const { getCurrentWebview } = await import("@tauri-apps/api/webview");
    unlisten = await getCurrentWebview().onDragDropEvent((event) => {
      if (event.payload.type === "over" || event.payload.type === "enter")
        dragging = true;
      else if (event.payload.type === "drop") {
        dragging = false;
        add(event.payload.paths);
      } else dragging = false;
    });
  });
  onDestroy(() => unlisten?.());
</script>

<h1>{t("new.title")}</h1>

<section class="card drop" class:dragging data-testid="drop-zone">
  <p>{t("new.drop")}</p>
  {#if isTauri()}
    <div class="row">
      <button onclick={pickFiles}>{t("new.addFiles")}</button>
      <button onclick={() => pickFolder("input")}>{t("new.addFolder")}</button>
    </div>
  {/if}
  <form
    class="row link"
    onsubmit={(event) => {
      event.preventDefault();
      addLink();
    }}
  >
    <input
      type="text"
      bind:value={link}
      placeholder={t("new.linkPlaceholder")}
      data-testid="link-input"
    />
    <button type="submit">{t("new.addLink")}</button>
  </form>
</section>

<h2>{t("new.inputs")}</h2>
{#if inputs.length === 0}
  <p class="muted">{t("new.noInputs")}</p>
{:else}
  <ul class="inputs">
    {#each inputs as input (input)}
      <li>
        <span title={input}>{displayName(input)}</span>
        <button
          aria-label="Remove"
          onclick={() => (inputs = inputs.filter((i) => i !== input))}>×</button
        >
      </li>
    {/each}
  </ul>
{/if}

<h2>{t("new.stems")}</h2>
<StemPicker bind:selected={stems} />

<h2>{t("new.mode")}</h2>
<div class="row">
  <label
    ><input type="radio" bind:group={mode} value="extract" />
    {t("new.mode.extract")}</label
  >
  <label
    ><input type="radio" bind:group={mode} value="without" />
    {t("new.mode.without")}</label
  >
</div>
{#if mode === "without"}
  <label class="row sub"
    ><input type="checkbox" bind:checked={keepResidual} />
    {t("new.residual")}</label
  >
{/if}

<div class="grid">
  <label>
    <span>{t("new.preset")}</span>
    <select bind:value={preset}>
      <option value="auto">{t("preset.auto")}</option>
      <option value="fast">{t("preset.fast")}</option>
      <option value="balanced">{t("preset.balanced")}</option>
      <option value="max">{t("preset.max")}</option>
    </select>
  </label>
  <label>
    <span>{t("new.format")}</span>
    <select bind:value={format}>
      <option value="wav">WAV (24-bit)</option>
      <option value="flac">FLAC</option>
      <option value="mp3">MP3 (320 kbps)</option>
    </select>
  </label>
  <label class="wide">
    <span>{t("new.output")}</span>
    <div class="row">
      <input type="text" bind:value={outputDir} data-testid="output-dir" />
      {#if isTauri()}<button onclick={() => pickFolder("output")}
          >{t("new.choose")}</button
        >{/if}
    </div>
  </label>
</div>

{#if hasLinks}
  <label class="row card rights" data-testid="rights">
    <input type="checkbox" bind:checked={rights} />
    {t("new.rights")}
  </label>
{/if}

<div class="row footer">
  {#if error}<span class="error" data-testid="job-error">{error}</span>{/if}
  {#if missing.length}
    <span
      >{t("new.missingModels")}
      {missing.join(", ")} —
      <a href={resolve("/models")}>{t("nav.models")}</a></span
    >
  {/if}
  <button
    class="primary"
    disabled={!canStart}
    onclick={start}
    data-testid="start">{t("new.start")}</button
  >
</div>

<style>
  .drop {
    border-style: dashed;
    text-align: center;
    display: grid;
    gap: 0.8rem;
    justify-items: center;
  }

  .drop.dragging {
    border-color: var(--accent);
    background: var(--accent-soft);
  }

  .link {
    width: min(560px, 100%);
  }

  .link input {
    flex: 1;
  }

  .inputs {
    display: grid;
    gap: 0.3rem;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .inputs li {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.3rem 0.4rem 0.3rem 0.8rem;
  }

  .inputs span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .sub {
    margin-top: 0.4rem;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-top: 1.5rem;
  }

  .grid label {
    display: grid;
    gap: 0.3rem;
  }

  .grid .wide {
    grid-column: 1 / -1;
  }

  .grid .wide input {
    flex: 1;
  }

  .rights {
    margin-top: 1.2rem;
    align-items: flex-start;
  }

  .footer {
    margin-top: 1.5rem;
    justify-content: flex-end;
  }
</style>
