<script lang="ts">
  // First-run quick win: the models recommended for this PC, installed with
  // one click once their licence notices are accepted, then the bundled
  // Creative Commons example song separated into every stem.
  import { onDestroy } from "svelte";
  import { errorMessage, type Schemas } from "$lib/api/client";
  import { bootstrap, separationReady } from "$lib/bootstrap.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { connection, onEvent } from "$lib/connection.svelte";
  import { openExternal } from "$lib/external";
  import { t } from "$lib/i18n.svelte";
  import { formatBytes } from "$lib/library";
  import {
    exampleJob,
    formatDuration,
    installProgress,
    pending,
    pendingMb,
    quickStep,
    recommendedModels,
  } from "$lib/quickstart";
  import { settings } from "$lib/settings.svelte";
  import { modelBytes } from "$lib/space";
  import { stemColor } from "$lib/stems";

  let { onstarted }: { onstarted?: () => void } = $props();

  let system = $state<Schemas["SystemOut"] | null>(null);
  let catalogue = $state<Schemas["ModelOut"][]>([]);
  let clip = $state<Schemas["ExampleOut"] | null>(null);
  let accepted = $state(false);
  let installing = $state(false);
  let progress = $state<Record<string, number>>({});
  let error = $state("");
  let starting = $state(false);

  const models = $derived(
    recommendedModels(system?.recommended_models, catalogue),
  );
  const step = $derived(
    quickStep({
      ready: connection.status === "ready" && system !== null,
      runtimeReady: separationReady(bootstrap.status),
      models,
      installing,
    }),
  );
  const overall = $derived(installProgress(models, progress));
  const outputDir = $derived(
    settings.outputDir.trim() ||
      (system ? `${system.data_dir}\\library\\example\\stems` : ""),
  );

  async function loadModels() {
    const api = connection.api;
    if (!api) return;
    const { data } = await api.GET("/models");
    if (data) catalogue = data;
    if (installing && models.length && models.every((m) => m.installed)) {
      installing = false;
    }
  }

  async function load() {
    const api = connection.api;
    if (!api) return;
    const [sys, example] = await Promise.all([
      api.GET("/system"),
      api.GET("/example"),
      loadModels(),
    ]);
    system = sys.data ?? null;
    clip = example.data ?? null;
  }

  $effect(() => {
    if (connection.status === "ready") void load();
  });

  async function install() {
    const api = connection.api;
    if (!api) return;
    installing = true;
    error = "";
    progress = {};
    for (const model of pending(models)) {
      const { error: problem } = await api.POST("/models/{model_id}/install", {
        params: { path: { model_id: model.id } },
        body: { accept_licence: true },
      });
      if (problem) {
        const body = problem as { code?: string };
        installing = false;
        error =
          body.code === "not_enough_space"
            ? t("models.space.short")
            : errorMessage(problem);
        return;
      }
    }
  }

  async function tryExample() {
    const api = connection.api;
    if (!api) return;
    starting = true;
    error = "";
    const added = await api.POST("/example");
    if (!added.data) {
      starting = false;
      error = errorMessage(added.error);
      return;
    }
    const job = await api.POST("/jobs", {
      body: exampleJob({
        path: added.data.path,
        outputDir: settings.outputDir,
        suggestedDir: added.data.output_dir,
        format: settings.format,
        allowCpu: settings.allowCpu,
      }),
    });
    starting = false;
    if (!job.data) {
      error = errorMessage(job.error);
      return;
    }
    onstarted?.();
  }

  const stop = onEvent((event) => {
    const id = String(event.model ?? "");
    if (!models.some((model) => model.id === id)) return;
    if (event.type === "model.install.progress") {
      progress = { ...progress, [id]: Number(event.progress ?? 0) };
    } else if (event.type === "model.install.done") {
      progress = { ...progress, [id]: 1 };
      void loadModels();
    } else if (event.type === "model.install.failed") {
      installing = false;
      error =
        event.code === "separation_missing"
          ? t("runtime.missing")
          : String(event.error ?? "");
    }
  });
  onDestroy(stop);

  const licenceTone: Record<string, string> = {
    permissive: "ok",
    disputed: "warn",
    none: "warn",
    "non-commercial": "danger",
    copyleft: "warn",
  };
</script>

<section class="quick" data-testid="quick-start">
  <header>
    <span class="caps">{t("quick.for")}</span>
    <h3>{t("quick.title")}</h3>
    <p class="muted">{t("quick.intro")}</p>
  </header>

  {#if step === "engine"}
    <p class="muted" data-testid="quick-wait">{t("quick.waitEngine")}</p>
  {:else if step !== "example"}
    {#if system}
      <p class="for">
        <span class="badge accent"
          >{t(`preset.${system.recommended_preset as "fast"}`)}</span
        >
        <span class="muted"
          >{system.gpu
            ? `${system.gpu.name} · ${system.gpu.total_mb} MB VRAM`
            : t("hw.cpuOnly")}</span
        >
      </p>
    {/if}
    <ul class="models">
      {#each models as model (model.id)}
        <li class="card model">
          <div class="head">
            <strong>{model.name}</strong>
            <span class="badge {licenceTone[model.licence_class] ?? ''}"
              >{model.licence_class}</span
            >
          </div>
          <div class="row tags">
            {#each model.stems as stem (stem)}
              <span class="stem-tag" style="--stem: {stemColor(stem)}"
                ><Icon name={stem} size={12} />{t(`stem.${stem}`)}</span
              >
            {/each}
          </div>
          <dl class="facts">
            <dt>{t("models.licence")}</dt>
            <dd>{model.licence}</dd>
            <dt>{t("models.licenceUrl")}</dt>
            <dd>
              <button
                type="button"
                class="link"
                onclick={() => void openExternal(model.licence_url)}
                >{model.licence_url} <Icon name="external" size={13} /></button
              >
            </dd>
            <dt>{t("models.space.download")}</dt>
            <dd>
              {model.installed
                ? t("quick.installed")
                : formatBytes(modelBytes(model.size_mb))}
            </dd>
          </dl>
          <details>
            <summary>{t("models.notice")}</summary>
            <pre>{model.notice}</pre>
          </details>
        </li>
      {/each}
    </ul>

    {#if step === "installing"}
      <div
        class="download"
        role="progressbar"
        aria-label={t("quick.installing")}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={Math.round(overall * 100)}
        data-testid="quick-progress"
      >
        <span class="label"
          >{t("quick.installing")} {Math.round(overall * 100)}%</span
        >
        <span class="track"
          ><span class="fill" style:width="{Math.max(2, overall * 100)}%"
          ></span></span
        >
      </div>
    {:else}
      {#if step === "runtime"}
        <p class="note warn" data-testid="quick-runtime">
          {t("quick.waitRuntime")}
        </p>
      {/if}
      <label class="row accept">
        <input
          type="checkbox"
          bind:checked={accepted}
          data-testid="quick-accept"
        />
        {t("quick.accept")}
      </label>
      <div class="row">
        <button
          class="primary"
          disabled={!accepted || step !== "install"}
          onclick={() => void install()}
          data-testid="quick-install"
          ><Icon name="download" size={16} />{pending(models).length > 1
            ? t("quick.installMany")
            : t("quick.install")}
          <span class="size">{formatBytes(modelBytes(pendingMb(models)))}</span
          ></button
        >
      </div>
    {/if}
  {:else}
    <div class="card example" data-testid="quick-example">
      <div class="head">
        <span class="cc"><Icon name="cc" size={20} /></span>
        <div>
          <h4>{t("quick.example.title")}</h4>
          <p class="muted">{t("quick.example.intro")}</p>
        </div>
      </div>
      {#if clip}
        <dl class="facts">
          <dt>{t("quick.example.song")}</dt>
          <dd>{clip.title} · {clip.artist}</dd>
          <dt>{t("quick.example.licence")}</dt>
          <dd>
            <button
              type="button"
              class="link"
              onclick={() => clip && void openExternal(clip.licence_url)}
              >{clip.licence_name} <Icon name="external" size={13} /></button
            >
          </dd>
          <dt>{t("quick.example.source")}</dt>
          <dd>
            <button
              type="button"
              class="link"
              onclick={() => clip && void openExternal(clip.page_url)}
              >{clip.page_url} <Icon name="external" size={13} /></button
            >
          </dd>
          <dt>{t("quick.example.length")}</dt>
          <dd>
            {formatDuration(clip.duration_s)} · {formatBytes(clip.size_bytes)}
          </dd>
          {#if clip.changes}
            <dt>{t("quick.example.changes")}</dt>
            <dd>{clip.changes}</dd>
          {/if}
          <dt>{t("quick.example.output")}</dt>
          <dd class="path" title={outputDir}>{outputDir}</dd>
        </dl>
      {/if}
      <div class="row">
        <button
          class="primary"
          disabled={starting || !clip}
          onclick={() => void tryExample()}
          data-testid="quick-try"
          ><Icon name="play" size={16} />{starting
            ? t("quick.example.starting")
            : t("quick.example.try")}</button
        >
      </div>
    </div>
    <p class="muted later">{t("quick.later")}</p>
  {/if}

  {#if error}<p class="error" data-testid="quick-error">{error}</p>{/if}
</section>

<style>
  .quick {
    display: grid;
    gap: 0.9rem;
  }

  header {
    display: grid;
    gap: 0.3rem;
  }

  header h3,
  header p {
    margin: 0;
  }

  header h3 {
    font-size: 1.2rem;
  }

  .for {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.6rem;
    margin: 0;
  }

  .models {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 0.8rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .model {
    display: grid;
    gap: 0.6rem;
    box-shadow:
      var(--shadow),
      0 0 0 1px var(--accent-soft);
  }

  .head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.6rem;
  }

  .tags {
    gap: 0.3rem;
  }

  .facts {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.3rem 0.9rem;
    margin: 0;
    font-size: 0.88rem;
  }

  .facts dt {
    color: var(--muted);
  }

  .facts dd {
    margin: 0;
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .facts .path {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  button.link {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    max-width: 100%;
    padding: 0;
    border: 0;
    background: none;
    box-shadow: none;
    color: var(--link);
    text-align: left;
    overflow-wrap: anywhere;
  }

  details summary {
    cursor: pointer;
    color: var(--muted);
    font-size: 0.85rem;
  }

  details pre {
    max-height: 9rem;
    overflow: auto;
    padding: 0.6rem;
    border-radius: var(--radius-sm);
    background: var(--well);
    font-size: 0.78rem;
    white-space: pre-wrap;
  }

  .note.warn {
    margin: 0;
    padding: 0.6rem 0.8rem;
    border-radius: var(--radius-sm);
    color: var(--warn);
    background: color-mix(in srgb, var(--warn) 10%, transparent);
    font-size: 0.88rem;
  }

  .accept {
    flex-wrap: nowrap;
    font-weight: 600;
  }

  .size {
    font-family: var(--font-mono);
    font-weight: 500;
    opacity: 0.8;
  }

  .download {
    display: grid;
    gap: 0.3rem;
    max-width: 420px;
  }

  .download .label {
    font-size: 0.82rem;
    color: var(--ok);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
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
    transition: width 0.4s ease;
  }

  .example {
    display: grid;
    gap: 0.9rem;
    border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
    box-shadow:
      var(--shadow),
      inset 0 3px 0 var(--accent);
  }

  .example h4 {
    margin: 0 0 0.3rem;
    font-size: 1.05rem;
  }

  .example .head p {
    margin: 0;
    font-size: 0.9rem;
  }

  .example .head {
    justify-content: flex-start;
  }

  .cc {
    display: grid;
    place-items: center;
    flex: none;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--surface-2);
    border: 1px solid var(--border);
    color: var(--accent-ink);
  }

  .later {
    margin: 0;
    font-size: 0.85rem;
  }
</style>
