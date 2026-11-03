<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import type { Schemas } from "$lib/api/client";
  import { connection, onEvent } from "$lib/connection.svelte";
  import { t } from "$lib/i18n.svelte";

  type Model = Schemas["ModelOut"];

  let { recommendedPreset = "" }: { recommendedPreset?: string } = $props();

  let models = $state<Model[]>([]);
  let reviewing = $state<Model | null>(null);
  let accepted = $state(false);
  let installing = $state<Record<string, boolean>>({});
  let errors = $state<Record<string, string>>({});

  async function load() {
    if (!connection.api) return;
    const { data } = await connection.api.GET("/models");
    if (data) models = data;
  }

  async function install(model: Model) {
    if (!connection.api) return;
    installing = { ...installing, [model.id]: true };
    errors = { ...errors, [model.id]: "" };
    await connection.api.POST("/models/{model_id}/install", {
      params: { path: { model_id: model.id } },
      body: { accept_licence: true },
    });
    reviewing = null;
    accepted = false;
  }

  const stop = onEvent((event) => {
    const id = String(event.model ?? "");
    if (event.type === "model.install.done") {
      installing = { ...installing, [id]: false };
      void load();
    } else if (event.type === "model.install.failed") {
      installing = { ...installing, [id]: false };
      errors = { ...errors, [id]: String(event.error ?? "") };
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

<ul class="models">
  {#each models as model (model.id)}
    <li class="card">
      <div class="head">
        <strong>{model.name}</strong>
        {#if recommendedPreset && model.recommended_for.includes(recommendedPreset)}
          <span class="badge ok">{t("models.recommended")}</span>
        {/if}
        <span class="badge {licenceTone[model.licence_class] ?? ''}"
          >{model.licence_class}</span
        >
      </div>
      <div class="muted">
        {model.stems.map((s) => t(`stem.${s}`)).join(", ")} · {model.size_mb} MB ·
        ~{model.vram_mb_fp16} MB VRAM
      </div>
      <div class="row actions">
        {#if model.installed}
          <span class="badge ok">{t("models.installed")}</span>
        {:else if installing[model.id]}
          <span class="badge">{t("models.installing")}</span>
        {:else}
          <button onclick={() => (reviewing = model)}
            >{t("models.install")}</button
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
  >
    <h2>{reviewing.name}</h2>
    <pre>{reviewing.notice}</pre>
    <label class="row">
      <input type="checkbox" bind:checked={accepted} />
      {t("models.accept")}
    </label>
    <div class="row end">
      <button onclick={() => (reviewing = null)}>{t("models.close")}</button>
      <button
        class="primary"
        disabled={!accepted}
        onclick={() => reviewing && install(reviewing)}
      >
        {t("models.download")}
      </button>
    </div>
  </div>
{/if}

<style>
  .models {
    display: grid;
    gap: 0.75rem;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.2rem;
  }

  .actions {
    margin-top: 0.6rem;
  }

  .backdrop {
    position: fixed;
    inset: 0;
    background: rgb(0 0 0 / 40%);
  }

  .dialog {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(560px, 92vw);
    z-index: 1;
  }

  pre {
    white-space: pre-wrap;
    font-family: inherit;
    background: var(--surface-2);
    border-radius: 8px;
    padding: 0.8rem;
  }

  .end {
    justify-content: flex-end;
    margin-top: 0.8rem;
  }
</style>
