<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import type { Schemas } from "$lib/api/client";
  import { bootstrap, separationReady } from "$lib/bootstrap.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import RuntimeNotice from "$lib/components/RuntimeNotice.svelte";
  import { connection, isTauri, onEvent } from "$lib/connection.svelte";
  import { i18n, t } from "$lib/i18n.svelte";
  import { stemColor } from "$lib/stems";

  type Model = Schemas["ModelOut"];

  let { recommendedPreset = "" }: { recommendedPreset?: string } = $props();

  let models = $state<Model[]>([]);
  let reviewing = $state<Model | null>(null);
  let accepted = $state(false);
  let installing = $state<Record<string, boolean>>({});
  // Download progress in [0, 1] per model, from model.install.progress events.
  let progress = $state<Record<string, number>>({});
  let errors = $state<Record<string, string>>({});

  // Scales for the size / VRAM meters (largest catalogue model ≈ full bar).
  const MAX_SIZE_MB = 900;
  const MAX_VRAM_MB = 4096;

  async function load() {
    if (!connection.api) return;
    const { data } = await connection.api.GET("/models");
    if (data) models = data;
  }

  async function install(model: Model) {
    if (!connection.api) return;
    installing = { ...installing, [model.id]: true };
    progress = { ...progress, [model.id]: 0 };
    errors = { ...errors, [model.id]: "" };
    await connection.api.POST("/models/{model_id}/install", {
      params: { path: { model_id: model.id } },
      body: { accept_licence: true },
    });
    reviewing = null;
    accepted = false;
  }

  // External page in the system browser (opener:default allows https URLs).
  async function openLicence(url: string) {
    if (!isTauri()) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  }

  function formatDate(value: string): string {
    const date = new Date(`${value}T00:00:00`);
    return Number.isNaN(date.getTime())
      ? value
      : date.toLocaleDateString(i18n.locale, { dateStyle: "long" });
  }

  const stop = onEvent((event) => {
    const id = String(event.model ?? "");
    if (event.type === "model.install.progress") {
      progress = { ...progress, [id]: Number(event.progress ?? 0) };
    } else if (event.type === "model.install.done") {
      installing = { ...installing, [id]: false };
      void load();
    } else if (event.type === "model.install.failed") {
      installing = { ...installing, [id]: false };
      errors = {
        ...errors,
        [id]:
          event.code === "separation_missing"
            ? t("runtime.missing")
            : String(event.error ?? ""),
      };
    }
  });

  onMount(load);
  onDestroy(stop);
  $effect(() => {
    if (connection.status === "ready") void load();
  });

  const licenceTone: Record<string, string> = {
    permissive: "ok",
    disputed: "warn",
    none: "warn",
    "non-commercial": "danger",
    copyleft: "warn",
  };
</script>

<RuntimeNotice />
<ul class="models">
  {#each models as model (model.id)}
    {@const recommended =
      recommendedPreset && model.recommended_for.includes(recommendedPreset)}
    <li class="card model" class:recommended class:installed={model.installed}>
      <div class="head">
        <span class="cube"><Icon name="models" size={20} /></span>
        <div class="title">
          <strong>{model.name}</strong>
          <div class="row tags">
            {#each model.stems as stem (stem)}
              <span class="stem-tag" style="--stem: {stemColor(stem)}"
                ><Icon name={stem} size={12} />{t(`stem.${stem}`)}</span
              >
            {/each}
          </div>
        </div>
        <div class="badges">
          {#if recommended}
            <span class="badge accent">{t("models.recommended")}</span>
          {/if}
          <span class="badge {licenceTone[model.licence_class] ?? ''}"
            >{model.licence_class}</span
          >
        </div>
      </div>
      <div class="meters">
        <div class="meter">
          <span class="muted">{t("models.size")}</span>
          <div class="progress">
            <div
              style="width: {Math.min(
                100,
                (model.size_mb / MAX_SIZE_MB) * 100,
              )}%"
            ></div>
          </div>
          <span class="value">{model.size_mb} MB</span>
        </div>
        <div class="meter">
          <span class="muted">VRAM</span>
          <div class="progress">
            <div
              style="width: {Math.min(
                100,
                (model.vram_mb_fp16 / MAX_VRAM_MB) * 100,
              )}%"
            ></div>
          </div>
          <span class="value">~{model.vram_mb_fp16} MB</span>
        </div>
      </div>
      <div class="row actions">
        {#if model.installed}
          <span class="badge ok"
            ><Icon name="check" size={12} strokeWidth={3} />{t(
              "models.installed",
            )}</span
          >
        {:else if installing[model.id]}
          <div
            class="download"
            role="progressbar"
            aria-label={t("models.installing")}
            aria-valuemin="0"
            aria-valuemax="100"
            aria-valuenow={Math.round((progress[model.id] ?? 0) * 100)}
            data-testid="download-progress"
          >
            <span class="label"
              >{t("models.installing")}
              {Math.round((progress[model.id] ?? 0) * 100)}%</span
            >
            <span class="track"
              ><span
                class="fill"
                style:width="{Math.max(2, (progress[model.id] ?? 0) * 100)}%"
              ></span></span
            >
          </div>
        {:else}
          <button
            class="small"
            disabled={!separationReady(bootstrap.status)}
            title={separationReady(bootstrap.status) ? "" : t("runtime.wait")}
            onclick={() => (reviewing = model)}
            ><Icon name="shield" size={14} />{t("models.install")}</button
          >
        {/if}
        {#if errors[model.id]}<span class="error">{errors[model.id]}</span>{/if}
      </div>
    </li>
  {/each}
</ul>

{#if reviewing}
  <div
    class="backdrop"
    role="presentation"
    onclick={() => (reviewing = null)}
  ></div>
  <div
    class="dialog card"
    role="dialog"
    aria-modal="true"
    aria-label={reviewing.name}
    data-testid="licence-dialog"
  >
    <div class="dialog-head">
      <span class="cube"><Icon name="shield" size={20} /></span>
      <div>
        <h3>{reviewing.name}</h3>
        <span class="badge {licenceTone[reviewing.licence_class] ?? ''}"
          >{reviewing.licence_class}</span
        >
      </div>
    </div>
    <dl class="facts">
      <dt>{t("models.licence")}</dt>
      <dd>{reviewing.licence}</dd>
      <dt>{t("models.licenceUrl")}</dt>
      <dd>
        <button
          type="button"
          class="link"
          data-testid="licence-url"
          onclick={() => reviewing && openLicence(reviewing.licence_url)}
          >{reviewing.licence_url} <Icon name="external" size={13} /></button
        >
      </dd>
      <dt>{t("models.verifiedOn")}</dt>
      <dd data-testid="verified-on">{formatDate(reviewing.verified_on)}</dd>
    </dl>
    <details>
      <summary>{t("models.notice")}</summary>
      <pre>{reviewing.notice}</pre>
    </details>
    <label class="row accept">
      <input type="checkbox" bind:checked={accepted} />
      {t("models.accept")}
    </label>
    <div class="row end">
      <button class="ghost" onclick={() => (reviewing = null)}
        >{t("models.close")}</button
      >
      <button
        class="primary"
        disabled={!accepted}
        onclick={() => reviewing && install(reviewing)}
      >
        <Icon name="download" size={16} />{t("models.download")}
      </button>
    </div>
  </div>
{/if}

<style>
  .download {
    display: grid;
    gap: 0.3rem;
    min-width: 180px;
    flex: 1;
    max-width: 320px;
  }

  .download .label {
    font-size: 0.78rem;
    color: var(--ok);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .download .track {
    height: 6px;
    border-radius: 3px;
    background: var(--border);
    overflow: hidden;
  }

  .download .fill {
    display: block;
    height: 100%;
    background: var(--ok);
    transition: width 0.4s ease;
  }

  .models {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 0.8rem;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .model {
    display: grid;
    gap: 0.9rem;
    align-content: start;
  }

  .model.recommended {
    border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
  }

  .head,
  .dialog-head {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 0.7rem;
  }

  .cube {
    display: grid;
    place-items: center;
    flex: none;
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: var(--accent-soft);
    color: var(--accent);
  }

  .installed .cube {
    background: color-mix(in srgb, var(--ok) 14%, transparent);
    color: var(--ok);
  }

  .title {
    flex: 1;
    display: grid;
    gap: 0.4rem;
    min-width: 0;
  }

  .badges {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.3rem;
  }

  .tags {
    gap: 0.3rem;
  }

  .meters {
    display: grid;
    gap: 0.45rem;
  }

  .meter {
    display: grid;
    grid-template-columns: 60px 1fr 80px;
    align-items: center;
    gap: 0.6rem;
    font-size: 0.8rem;
  }

  .value {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .backdrop {
    position: fixed;
    inset: 0;
    background: rgb(0 0 0 / 55%);
    backdrop-filter: blur(4px);
    z-index: 10;
  }

  .dialog {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(600px, 92vw);
    max-height: 88vh;
    overflow: auto;
    z-index: 11;
    display: grid;
    gap: 1rem;
    background: var(--surface);
  }

  h3 {
    margin: 0 0 0.3rem;
    font-size: 1.15rem;
  }

  .facts {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.5rem 1rem;
    margin: 0;
  }

  dt {
    color: var(--muted);
    font-size: 0.85rem;
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .link {
    display: inline;
    padding: 0;
    border: none;
    background: none;
    color: var(--accent);
    text-align: left;
    text-decoration: underline;
    overflow-wrap: anywhere;
  }

  .link :global(.icon) {
    display: inline-block;
    vertical-align: -2px;
  }

  summary {
    cursor: pointer;
    color: var(--muted);
    font-size: 0.85rem;
  }

  pre {
    white-space: pre-wrap;
    font-family: inherit;
    font-size: 0.85rem;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 0.8rem;
  }

  .accept {
    flex-wrap: nowrap;
  }

  .end {
    justify-content: flex-end;
  }
</style>
