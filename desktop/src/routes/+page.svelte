<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import Icon from "$lib/components/Icon.svelte";
  import RuntimeNotice from "$lib/components/RuntimeNotice.svelte";
  import StemPicker from "$lib/components/StemPicker.svelte";
  import Waveform from "$lib/components/Waveform.svelte";
  import { connection, isTauri } from "$lib/connection.svelte";
  import { t } from "$lib/i18n.svelte";
  import type { IconName } from "$lib/icons";
  import { displayName } from "$lib/jobs";
  import { settings } from "$lib/settings.svelte";
  import { stemColor, type Stem } from "$lib/stems";

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

  type Mode = "extract" | "without" | "both";

  const MODES: { value: Mode; icon: IconName }[] = [
    { value: "extract", icon: "scissors" },
    { value: "without", icon: "mix" },
    { value: "both", icon: "download" },
  ];

  let inputs = $state<string[]>([]);
  let link = $state("");
  let stems = $state<Stem[]>(["vocals"]);
  let mode = $state<Mode>("extract");
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

  const isLink = (input: string) => /^https?:\/\//i.test(input);
  const accent = $derived(stemColor(stems[0] ?? "other"));
  const hasLinks = $derived(inputs.some(isLink));
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

<header class="page-head">
  <div>
    <h1>{t("new.title")}</h1>
    <p>{t("new.subtitle")}</p>
  </div>
</header>
<RuntimeNotice />

<section class="card drop" class:dragging data-testid="drop-zone">
  <div class="drop-wave" aria-hidden="true">
    <Waveform seed="drop-zone" bars={72} height={56} progress={0} />
  </div>
  <span class="drop-icon"><Icon name="upload" size={26} /></span>
  <p class="drop-title">{t("new.drop")}</p>
  {#if isTauri()}
    <div class="row">
      <button onclick={pickFiles}
        ><Icon name="plus" size={16} />{t("new.addFiles")}</button
      >
      <button onclick={() => pickFolder("input")}
        ><Icon name="folder" size={16} />{t("new.addFolder")}</button
      >
    </div>
  {/if}
  <form
    class="link"
    onsubmit={(event) => {
      event.preventDefault();
      addLink();
    }}
  >
    <Icon name="link" size={16} />
    <input
      type="text"
      bind:value={link}
      placeholder={t("new.linkPlaceholder")}
      data-testid="link-input"
    />
    <button type="submit" class="small">{t("new.addLink")}</button>
  </form>
</section>

<h2>
  {t("new.inputs")}
  {#if inputs.length}<span class="count">{inputs.length}</span>{/if}
</h2>
{#if inputs.length === 0}
  <p class="muted empty">{t("new.noInputs")}</p>
{:else}
  <ul class="inputs">
    {#each inputs as input (input)}
      <li>
        <span class="kind"
          ><Icon name={isLink(input) ? "link" : "other"} size={16} /></span
        >
        <span class="name" title={input}>{displayName(input)}</span>
        <span class="thumb"
          ><Waveform seed={input} bars={28} height={22} color={accent} /></span
        >
        <button
          class="ghost small"
          aria-label="Remove"
          onclick={() => (inputs = inputs.filter((i) => i !== input))}
          ><Icon name="x" size={14} /></button
        >
      </li>
    {/each}
  </ul>
{/if}

<h2>{t("new.stems")}</h2>
<StemPicker bind:selected={stems} />

<h2>{t("new.mode")}</h2>
<div class="modes" role="radiogroup" aria-label={t("new.mode")}>
  {#each MODES as option (option.value)}
    <label class="mode" class:on={mode === option.value}>
      <input type="radio" bind:group={mode} value={option.value} />
      <span class="mode-icon"><Icon name={option.icon} size={20} /></span>
      <span class="mode-text">
        <strong>{t(`new.mode.${option.value}`)}</strong>
        <small class="muted">{t(`new.mode.${option.value}.hint`)}</small>
      </span>
    </label>
  {/each}
</div>
{#if mode !== "extract"}
  <label class="row sub"
    ><input type="checkbox" bind:checked={keepResidual} />
    {t("new.residual")}</label
  >
{/if}

<h2>{t("new.settings")}</h2>
<div class="card grid">
  <label>
    <span class="field">{t("new.preset")}</span>
    <select bind:value={preset}>
      <option value="auto">{t("preset.auto")}</option>
      <option value="fast">{t("preset.fast")}</option>
      <option value="balanced">{t("preset.balanced")}</option>
      <option value="max">{t("preset.max")}</option>
    </select>
  </label>
  <label>
    <span class="field">{t("new.format")}</span>
    <select bind:value={format}>
      <option value="wav">WAV (24-bit)</option>
      <option value="flac">FLAC</option>
      <option value="mp3">MP3 (320 kbps)</option>
    </select>
  </label>
  <label class="wide">
    <span class="field">{t("new.output")}</span>
    <div class="row">
      <input type="text" bind:value={outputDir} data-testid="output-dir" />
      {#if isTauri()}<button onclick={() => pickFolder("output")}
          ><Icon name="folder" size={16} />{t("new.choose")}</button
        >{/if}
    </div>
  </label>
</div>

{#if hasLinks}
  <label class="row card rights" data-testid="rights">
    <input type="checkbox" bind:checked={rights} />
    <span>{t("new.rights")}</span>
  </label>
{/if}

<div class="footer card">
  <div class="summary">
    {#each stems as stem (stem)}
      <span class="stem-tag" style="--stem: {stemColor(stem)}"
        ><Icon name={stem} size={13} />{t(`stem.${stem}`)}</span
      >
    {/each}
    <span class="muted">· {t(`new.mode.${mode}`)}</span>
  </div>
  <div class="row">
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
      data-testid="start"><Icon name="play" size={16} />{t("new.start")}</button
    >
  </div>
</div>

<style>
  .drop {
    position: relative;
    overflow: hidden;
    border: 1.5px dashed var(--border-strong);
    background: var(--surface);
    text-align: center;
    display: grid;
    gap: 0.9rem;
    justify-items: center;
    padding: 2rem 1.2rem 1.5rem;
    transition:
      border-color 0.2s ease,
      background 0.2s ease;
  }

  .drop-wave {
    position: absolute;
    inset: auto 0 0;
    opacity: 0.6;
    pointer-events: none;
    --wave-off: var(--accent-soft);
  }

  .drop.dragging {
    border-color: var(--accent);
    background: var(--accent-soft);
  }

  .drop > :not(.drop-wave) {
    position: relative;
  }

  .drop-icon {
    display: grid;
    place-items: center;
    width: 56px;
    height: 56px;
    border-radius: 16px;
    background: var(--gradient);
    color: #fff;
    box-shadow: 0 10px 30px rgb(143 123 255 / 35%);
  }

  .drop-title {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.1rem;
    font-weight: 600;
  }

  .link {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    width: min(560px, 100%);
    padding: 0.25rem 0.3rem 0.25rem 0.75rem;
    border: 1px solid var(--border-strong);
    border-radius: 12px;
    background: var(--surface-2);
    color: var(--muted);
  }

  .link input {
    flex: 1;
    border: none;
    background: transparent;
    padding: 0.35rem 0;
    color: var(--fg);
  }

  .link:focus-within {
    border-color: var(--accent);
  }

  .link input:focus-visible {
    outline: none;
  }

  .count {
    margin-left: 0.3rem;
    padding: 0 0.45rem;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
  }

  .empty {
    margin: 0;
  }

  .inputs {
    display: grid;
    gap: 0.4rem;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .inputs li {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) 140px auto;
    align-items: center;
    gap: 0.75rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.4rem 0.4rem 0.4rem 0.6rem;
  }

  .kind {
    display: grid;
    place-items: center;
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: var(--surface-3);
    color: var(--muted);
  }

  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .modes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.6rem;
  }

  .mode {
    position: relative;
    display: flex;
    align-items: flex-start;
    gap: 0.7rem;
    padding: 0.85rem 0.9rem;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: var(--surface);
    cursor: pointer;
    transition:
      border-color 0.15s ease,
      background 0.15s ease;
  }

  .mode:hover {
    border-color: var(--border-strong);
  }

  .mode input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }

  .mode:has(input:focus-visible) {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .mode-icon {
    display: grid;
    place-items: center;
    flex: none;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: var(--surface-3);
    color: var(--muted);
  }

  .mode-text {
    display: grid;
    gap: 0.15rem;
  }

  .mode.on {
    border-color: var(--accent);
    background: linear-gradient(180deg, var(--accent-soft), var(--surface));
  }

  .mode.on .mode-icon {
    background: var(--gradient);
    color: #fff;
  }

  .sub {
    margin-top: 0.6rem;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
  }

  .grid label {
    display: grid;
    gap: 0.35rem;
  }

  .field {
    font-size: 0.85rem;
    color: var(--muted);
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
    flex-wrap: nowrap;
    border-color: color-mix(in srgb, var(--warn) 40%, var(--border));
  }

  .footer {
    position: sticky;
    bottom: 1rem;
    margin-top: 1.8rem;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.8rem;
    padding: 0.8rem 0.9rem 0.8rem 1.1rem;
    backdrop-filter: blur(12px);
  }

  .summary {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.35rem;
  }

  @media (max-width: 760px) {
    .modes,
    .grid {
      grid-template-columns: 1fr;
    }
  }
</style>
