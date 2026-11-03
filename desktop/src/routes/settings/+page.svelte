<script lang="ts">
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import { isTauri } from "$lib/connection.svelte";
  import { LOCALES, t, type Locale } from "$lib/i18n.svelte";
  import { saveSettings, settings } from "$lib/settings.svelte";

  const locales = Object.entries(LOCALES) as [Locale, string][];

  let appVersion = $state("");
  let appUpdate = $state("");
  let ytdlp = $state("");
  let ytdlpNewer = $state(false);
  let busy = $state(false);

  if (isTauri()) {
    void import("@tauri-apps/api/app").then(async ({ getVersion }) => {
      appVersion = await getVersion();
    });
  }

  async function checkApp() {
    busy = true;
    try {
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check();
      if (!update) {
        appUpdate = t("updates.latest");
        return;
      }
      appUpdate = `${t("updates.installing")} ${update.version}…`;
      await update.downloadAndInstall();
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
    } catch (error) {
      appUpdate = String(error);
    } finally {
      busy = false;
    }
  }

  async function checkYtDlp() {
    busy = true;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const versions = await invoke<{ installed: string; latest: string }>(
        "check_ytdlp",
      );
      ytdlpNewer = versions.installed !== versions.latest;
      ytdlp = ytdlpNewer
        ? `${versions.installed} → ${versions.latest}`
        : `${versions.installed} · ${t("updates.latest")}`;
    } catch (error) {
      ytdlp = String(error);
    } finally {
      busy = false;
    }
  }

  async function updateYtDlp() {
    busy = true;
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      const version = await invoke<string>("update_ytdlp");
      ytdlp = `${version} · ${t("updates.latest")}`;
      ytdlpNewer = false;
    } catch (error) {
      ytdlp = String(error);
    } finally {
      busy = false;
    }
  }

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

<header class="page-head">
  <h1>{t("settings.title")}</h1>
</header>

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

{#if isTauri()}
  <div class="card form updates" data-testid="updates">
    <h2>{t("updates.title")}</h2>
    <div class="line">
      <span>{t("updates.app")} <span class="muted">{appVersion}</span></span>
      <button disabled={busy} onclick={checkApp}>{t("updates.check")}</button>
    </div>
    {#if appUpdate}<p class="muted">{appUpdate}</p>{/if}
    <div class="line">
      <span>yt-dlp</span>
      <button disabled={busy} onclick={checkYtDlp}
        >{t("updates.checkYtDlp")}</button
      >
    </div>
    {#if ytdlp}
      <p class="muted">
        {ytdlp}
        {#if ytdlpNewer}<button
            class="small primary"
            disabled={busy}
            onclick={updateYtDlp}>{t("updates.install")}</button
          >{/if}
      </p>
    {/if}
  </div>
{/if}

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

  .updates {
    margin-top: 1.2rem;
  }

  .updates h2 {
    margin: 0;
    font-size: 1rem;
  }

  .updates p {
    margin: 0;
    word-break: break-word;
  }

  .line {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .form input[type="text"] {
    flex: 1;
  }
</style>
