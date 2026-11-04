<script lang="ts">
  import { onDestroy } from "svelte";
  import type { Schemas } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import { connection, isTauri, onEvent } from "$lib/connection.svelte";
  import { sendToNewJob } from "$lib/handoff.svelte";
  import { t } from "$lib/i18n.svelte";
  import { formatBytes } from "$lib/library";

  type Entry = Schemas["CatalogEntryOut"];
  type File = Schemas["CatalogFileOut"];

  let source = $state<"ccmixter" | "archive">("ccmixter");
  let query = $state("");
  let results = $state<Entry[]>([]);
  let searching = $state(false);
  let error = $state("");
  let files = $state<Record<string, File[]>>({});
  // Per download URL: "busy", "failed: …" or the local path once done.
  let downloads = $state<Record<string, string>>({});
  // ccMixter entries the user added by hand: entry id -> library path.
  let attached = $state<Record<string, string>>({});
  let attachError = $state<Record<string, string>>({});

  async function attach(entry: Entry) {
    if (!connection.api) return;
    const { open } = await import("@tauri-apps/plugin-dialog");
    const path = await open({
      filters: [
        { name: "Audio", extensions: ["mp3", "flac", "wav", "ogg", "m4a"] },
      ],
    });
    if (typeof path !== "string") return;
    const { data, error: problem } = await connection.api.POST(
      "/catalog/attach",
      {
        body: {
          source: entry.source,
          path,
          title: entry.title,
          artist: entry.artist,
          licence_name: entry.licence_name,
          licence_url: entry.licence_url,
          page_url: entry.page_url,
        },
      },
    );
    if (data) attached = { ...attached, [entry.id]: data.path };
    else
      attachError = {
        ...attachError,
        [entry.id]: (problem as { detail?: string })?.detail ?? "",
      };
  }

  async function search() {
    if (!connection.api || !query.trim()) return;
    searching = true;
    error = "";
    const { data, error: problem } = await connection.api.GET(
      "/catalog/search",
      { params: { query: { source, q: query.trim() } } },
    );
    searching = false;
    if (problem) {
      error = (problem as { detail?: string }).detail ?? t("catalog.error");
      results = [];
      return;
    }
    results = data ?? [];
  }

  async function loadFiles(entry: Entry) {
    if (!connection.api) return;
    const { data } = await connection.api.GET(
      "/catalog/archive/{identifier}/files",
      { params: { path: { identifier: entry.id } } },
    );
    files = { ...files, [entry.id]: data ?? [] };
  }

  function filesOf(entry: Entry): File[] {
    return entry.source === "archive" ? (files[entry.id] ?? []) : entry.files;
  }

  async function download(entry: Entry, file: File) {
    if (!connection.api) return;
    downloads = { ...downloads, [file.url]: "busy" };
    await connection.api.POST("/catalog/download", {
      body: {
        source: entry.source,
        file,
        title: entry.source === "archive" ? file.title : entry.title,
        artist: entry.artist,
        licence_name: entry.licence_name,
        licence_url: entry.licence_url,
        page_url: entry.page_url,
      },
    });
  }

  async function openPage(url: string) {
    if (!isTauri()) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  }

  const stop = onEvent((event) => {
    const url = String(event.url ?? "");
    if (event.type === "catalog.download.done")
      downloads = { ...downloads, [url]: String(event.path) };
    else if (event.type === "catalog.download.failed")
      downloads = { ...downloads, [url]: `failed: ${String(event.error)}` };
  });
  onDestroy(stop);
</script>

<header class="page-head">
  <div>
    <h1>{t("catalog.title")}</h1>
    <p>{t("catalog.subtitle")}</p>
  </div>
</header>

<section class="card search">
  <div class="row">
    <select bind:value={source} aria-label={t("catalog.source")}>
      <option value="ccmixter">ccMixter</option>
      <option value="archive">Internet Archive</option>
    </select>
    <input
      type="search"
      bind:value={query}
      placeholder={t("catalog.placeholder")}
      onkeydown={(e) => e.key === "Enter" && search()}
    />
    <button
      class="primary"
      onclick={search}
      disabled={searching || !query.trim()}
      ><Icon name="search" size={15} />{t("catalog.search")}</button
    >
  </div>
  <p class="muted note">{t("catalog.note")}</p>
  {#if error}<p class="error">{error}</p>{/if}
</section>

{#if searching}
  <p class="muted">{t("catalog.searching")}</p>
{:else if results.length === 0 && query && !error}
  <p class="muted">{t("catalog.none")}</p>
{/if}

<ul class="results">
  {#each results as entry (entry.source + entry.id)}
    <li class="card entry" data-testid="catalog-entry">
      <div class="head">
        <div class="who">
          <strong>{entry.title}</strong>
          <span class="muted">{entry.artist}</span>
        </div>
        <button class="small ghost" onclick={() => openPage(entry.page_url)}
          ><Icon name="external" size={13} />{t("catalog.page")}</button
        >
      </div>
      <div class="row licence">
        <button class="badge link" onclick={() => openPage(entry.licence_url)}
          >{entry.licence_name}</button
        >
        {#if entry.restrictions.includes("NC")}
          <span class="badge warn">{t("catalog.nc")}</span>
        {/if}
        {#if entry.restrictions.includes("ND")}
          <span class="badge danger">{t("catalog.nd")}</span>
        {/if}
      </div>
      {#if entry.restrictions.includes("ND")}
        <p class="warning">{t("catalog.ndWarning")}</p>
      {/if}

      {#if entry.source === "ccmixter"}
        <!-- ccMixter does not allow automated downloads: the user downloads on
             its site and adds the file here, which keeps the credits. -->
        <p class="muted hint">{t("catalog.ccmixterHint")}</p>
        <div class="row manual">
          <button class="small" onclick={() => openPage(entry.page_url)}
            ><Icon name="external" size={13} />{t("catalog.openSite")}</button
          >
          {#if attached[entry.id]}
            <button
              class="small primary"
              onclick={() => sendToNewJob([attached[entry.id]])}
              ><Icon name="plus" size={13} />{t("catalog.use")}</button
            >
          {:else if isTauri()}
            <button class="small" onclick={() => attach(entry)}
              ><Icon name="upload" size={13} />{t("catalog.attach")}</button
            >
          {/if}
        </div>
        {#if attachError[entry.id]}<p class="error">
            {attachError[entry.id]}
          </p>{/if}
      {/if}
      {#if entry.source === "archive" && !files[entry.id]}
        <button class="small" onclick={() => loadFiles(entry)}
          >{t("catalog.showFiles")}</button
        >
      {/if}
      <ul class="files">
        {#each entry.source === "archive" ? filesOf(entry) : [] as file (file.url)}
          {@const state = downloads[file.url]}
          <li>
            <span class="name" title={file.name}>{file.title}</span>
            {#if file.size_bytes}<span class="muted size"
                >{formatBytes(file.size_bytes)}</span
              >{/if}
            {#if state === "busy"}
              <span class="muted">{t("catalog.downloading")}</span>
            {:else if state?.startsWith("failed")}
              <span class="error" title={state}>{t("catalog.failed")}</span>
            {:else if state}
              <button
                class="small primary"
                onclick={() => sendToNewJob([state])}
                ><Icon name="plus" size={13} />{t("catalog.use")}</button
              >
            {:else}
              <button class="small" onclick={() => download(entry, file)}
                ><Icon name="download" size={13} />{t(
                  "catalog.download",
                )}</button
              >
            {/if}
          </li>
        {/each}
      </ul>
    </li>
  {/each}
</ul>

<style>
  .search .row {
    gap: 0.6rem;
  }

  .search input {
    flex: 1;
  }

  .search button,
  .entry button {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .note {
    margin: 0.6rem 0 0;
    font-size: 0.82rem;
  }

  .results {
    list-style: none;
    margin: 1rem 0;
    padding: 0;
    display: grid;
    gap: 0.8rem;
  }

  .entry {
    display: grid;
    gap: 0.5rem;
    min-width: 0;
  }

  .head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.8rem;
  }

  .who {
    display: grid;
    min-width: 0;
  }

  .who strong,
  .who span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .licence {
    gap: 0.4rem;
    flex-wrap: wrap;
  }

  .badge.link {
    cursor: pointer;
    border: 0;
  }

  .warning {
    margin: 0;
    font-size: 0.82rem;
    color: var(--danger);
  }

  .hint {
    margin: 0;
    font-size: 0.82rem;
  }

  .manual {
    gap: 0.5rem;
  }

  .files {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.3rem;
  }

  .files li {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.3rem 0;
    border-top: 1px solid var(--border);
  }

  .files .name {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .size {
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }
</style>
