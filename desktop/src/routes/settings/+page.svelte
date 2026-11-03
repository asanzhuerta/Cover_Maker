<script lang="ts">
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import { isTauri } from "$lib/connection.svelte";
  import { LOCALES, t, type Locale } from "$lib/i18n.svelte";
  import { saveSettings, settings } from "$lib/settings.svelte";

  const locales = Object.entries(LOCALES) as [Locale, string][];

  async function chooseOutput() {
    const { open } = await import("@tauri-apps/plugin-dialog");
    const chosen = await open({ directory: true });
    if (typeof chosen === "string") {
      settings.outputDir = chosen;
      saveSettings();
    }
  }

  function showWelcome() {
    settings.welcomed = false;
    saveSettings();
    void goto(resolve("/welcome"));
  }
</script>

<h1>{t("settings.title")}</h1>

<div class="card form">
  <label>
    <span>{t("settings.language")}</span>
    <select
      bind:value={settings.locale}
      onchange={saveSettings}
      data-testid="locale"
    >
      {#each locales as [code, name] (code)}
        <option value={code}>{name}</option>
      {/each}
    </select>
  </label>

  <label>
    <span>{t("settings.theme")}</span>
    <select bind:value={settings.theme} onchange={saveSettings}>
      <option value="system">{t("settings.theme.system")}</option>
      <option value="light">{t("settings.theme.light")}</option>
      <option value="dark">{t("settings.theme.dark")}</option>
    </select>
  </label>

  <label>
    <span>{t("settings.output")}</span>
    <div class="row">
      <input
        type="text"
        bind:value={settings.outputDir}
        onchange={saveSettings}
      />
      {#if isTauri()}<button onclick={chooseOutput}>{t("new.choose")}</button
        >{/if}
    </div>
  </label>

  <label>
    <span>{t("settings.format")}</span>
    <select bind:value={settings.format} onchange={saveSettings}>
      <option value="wav">WAV (24-bit)</option>
      <option value="flac">FLAC</option>
      <option value="mp3">MP3 (320 kbps)</option>
    </select>
  </label>

  <label class="row">
    <input
      type="checkbox"
      bind:checked={settings.allowCpu}
      onchange={saveSettings}
    />
    {t("settings.cpu")}
  </label>

  <div><button onclick={showWelcome}>{t("settings.reset")}</button></div>
</div>

<style>
  .form {
    display: grid;
    gap: 1.1rem;
    max-width: 560px;
  }

  .form label:not(.row) {
    display: grid;
    gap: 0.3rem;
  }

  .form input[type="text"] {
    flex: 1;
  }
</style>
