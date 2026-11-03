<script lang="ts">
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import type { Schemas } from "$lib/api/client";
  import ModelList from "$lib/components/ModelList.svelte";
  import { connection } from "$lib/connection.svelte";
  import { t } from "$lib/i18n.svelte";
  import { saveSettings, settings } from "$lib/settings.svelte";

  let accepted = $state(settings.welcomed);
  let system = $state<Schemas["SystemOut"] | null>(null);

  $effect(() => {
    if (connection.status === "ready" && connection.api && !system) {
      void connection.api
        .GET("/system")
        .then(({ data }) => (system = data ?? null));
    }
  });

  function finish() {
    settings.welcomed = true;
    saveSettings();
    void goto(resolve("/"));
  }
</script>

<h1>{t("welcome.title")}</h1>
<p>{t("welcome.intro")}</p>

<section class="card legal">
  <p>{t("welcome.legal")}</p>
  <label class="row">
    <input type="checkbox" bind:checked={accepted} data-testid="accept-terms" />
    {t("welcome.accept")}
  </label>
</section>

{#if accepted}
  <h2>{t("welcome.hardware")}</h2>
  {#if system}
    <div class="card hw">
      <div>{system.cpu} · {system.ram_gb} GB RAM</div>
      {#if system.gpu}
        <div>{system.gpu.name} · {system.gpu.total_mb} MB VRAM</div>
      {:else}
        <div class="muted">{t("hw.cpuOnly")}</div>
      {/if}
      <div class="row">
        <span class="badge">{t("hw.tier")}: {system.tier}</span>
        <span class="badge ok"
          >{t("hw.preset")}: {t(
            `preset.${system.recommended_preset as "fast"}`,
          )}</span
        >
      </div>
    </div>
  {:else}
    <p class="muted">{t("engine.starting")}</p>
  {/if}

  <h2>{t("welcome.models")}</h2>
  <p class="muted">{t("welcome.modelsHint")}</p>
  <ModelList recommendedPreset={system?.recommended_preset ?? ""} />

  <div class="row footer">
    <button class="primary" onclick={finish} data-testid="welcome-finish"
      >{t("welcome.finish")}</button
    >
  </div>
{/if}

<style>
  .legal {
    border-left: 4px solid var(--accent);
  }

  .hw {
    display: grid;
    gap: 0.3rem;
  }

  .footer {
    margin-top: 1.5rem;
    justify-content: flex-end;
  }
</style>
