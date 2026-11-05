<script lang="ts">
  import { SvelteSet } from "svelte/reactivity";
  import type { Schemas } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import { connection, isTauri } from "$lib/connection.svelte";
  import { sendToNewJob } from "$lib/handoff.svelte";
  import { t, type MessageKey } from "$lib/i18n.svelte";
  import {
    baseName,
    formatBytes,
    newItemIds,
    selectedInputs,
    statusTone,
    syncSummary,
  } from "$lib/library";

  type Collection = Schemas["CollectionOut"];
  type Item = Schemas["CollectionItemOut"];

  let collections = $state<Collection[]>([]);
  let open = $state<number | null>(null);
  let items = $state<Item[]>([]);
  let done = $state<Record<number, string[]>>({});
  const selected = new SvelteSet<number>();
  let link = $state("");
  let message = $state("");
  let busy = $state(false);
  let usage = $state<Schemas["StorageOut"] | null>(null);
  let freed = $state<number | null>(null);
  let summary = $state<{ id: number; parts: [string, number][] } | null>(null);

  const KIND: Record<string, MessageKey> = {
    folder: "library.kind.folder",
    video_playlist: "library.kind.video",
    playlist_file: "library.kind.file",
  };
  const SYNC: Record<string, MessageKey> = {
    added: "library.sync.added",
    removed: "library.sync.removed",
    unchanged: "library.sync.unchanged",
    needs_review: "library.sync.review",
    unavailable: "library.sync.unavailable",
  };
  const STATUS: Record<string, MessageKey> = {
    ready: "library.status.ready",
    needs_review: "library.status.review",
    unavailable: "library.status.unavailable",
  };

  async function load() {
    if (!connection.api) return;
    const [list, storage] = await Promise.all([
      connection.api.GET("/library"),
      connection.api.GET("/storage"),
    ]);
    collections = list.data ?? [];
    usage = storage.data ?? null;
    if (open !== null) await loadItems(open);
  }

  async function loadItems(id: number) {
    if (!connection.api) return;
    const params = { params: { path: { collection_id: id } } };
    const [list, state] = await Promise.all([
      connection.api.GET("/library/{collection_id}/items", params),
      connection.api.GET("/library/{collection_id}/state", params),
    ]);
    items = list.data ?? [];
    done = Object.fromEntries(
      (state.data ?? []).map((s) => [s.item_id, Object.keys(s.outputs)]),
    );
  }

  $effect(() => {
    if (connection.status === "ready") void load();
  });

  async function toggle(id: number) {
    selected.clear();
    if (open === id) {
      open = null;
      return;
    }
    open = id;
    await loadItems(id);
  }

  async function run(task: () => Promise<{ error?: unknown }>) {
    busy = true;
    message = "";
    try {
      const { error } = await task();
      if (error)
        message = (error as { detail?: string }).detail ?? String(error);
      await load();
    } finally {
      busy = false;
    }
  }

  async function sync(id: number) {
    if (!connection.api) return;
    const api = connection.api;
    await run(async () => {
      const result = await api.POST("/library/{collection_id}/sync", {
        params: { path: { collection_id: id } },
      });
      if (result.data) summary = { id, parts: syncSummary(result.data) };
      return result;
    });
  }

  function selectNew() {
    selected.clear();
    for (const id of newItemIds(items, done)) selected.add(id);
  }

  async function addFolder() {
    if (!connection.api) return;
    const { open: choose } = await import("@tauri-apps/plugin-dialog");
    const path = await choose({ directory: true });
    if (typeof path !== "string") return;
    const api = connection.api;
    await run(async () => {
      const created = await api.POST("/library/folders", { body: { path } });
      if (created.data) await sync(created.data.id);
      return created;
    });
  }

  async function addPlaylist() {
    if (!connection.api || !link.trim()) return;
    const api = connection.api;
    await run(async () => {
      const created = await api.POST("/library/playlists", {
        body: { link: link.trim() },
      });
      if (created.data) {
        link = "";
        await sync(created.data.id);
      }
      return created;
    });
  }

  async function importFile() {
    if (!connection.api) return;
    const { open: choose } = await import("@tauri-apps/plugin-dialog");
    const file = await choose({
      filters: [{ name: "Playlist", extensions: ["m3u", "m3u8", "csv"] }],
    });
    if (typeof file !== "string") return;
    // Look for the songs in every watched folder.
    const search = collections
      .filter((c) => c.kind === "folder")
      .map((c) => c.source);
    const api = connection.api;
    await run(async () => {
      const created = await api.POST("/library/imports", {
        body: { file, search },
      });
      for (const c of created.data ?? []) await sync(c.id);
      return created;
    });
  }

  async function remove(id: number) {
    if (!connection.api) return;
    const api = connection.api;
    if (open === id) open = null;
    await run(() =>
      api.DELETE("/library/{collection_id}", {
        params: { path: { collection_id: id } },
      }),
    );
  }

  async function chooseFile(item: Item) {
    if (!connection.api) return;
    const { open: choose } = await import("@tauri-apps/plugin-dialog");
    const path = await choose({
      filters: [
        {
          name: "Audio",
          extensions: ["wav", "flac", "mp3", "m4a", "ogg", "opus", "aiff"],
        },
      ],
    });
    if (typeof path !== "string") return;
    await setMatch(item, path);
  }

  async function setMatch(item: Item, path: string | null) {
    if (!connection.api) return;
    const api = connection.api;
    await run(() =>
      api.PUT("/library/items/{item_id}/match", {
        params: { path: { item_id: item.id } },
        body: { path },
      }),
    );
  }

  function pick(id: number, on: boolean) {
    if (on) selected.add(id);
    else selected.delete(id);
  }

  async function cleanUp() {
    if (!connection.api) return;
    const api = connection.api;
    await run(async () => {
      const result = await api.POST("/storage/cleanup");
      freed = result.data?.freed_bytes ?? null;
      return result;
    });
  }

  const ready = $derived(selectedInputs(items, selected));
</script>

<header class="page-head">
  <div>
    <h1>{t("library.title")}</h1>
    <p>{t("library.subtitle")}</p>
  </div>
</header>

<section class="card add">
  <div class="row">
    {#if isTauri()}
      <button onclick={addFolder} disabled={busy}
        ><Icon name="folder" size={15} />{t("library.addFolder")}</button
      >
      <button onclick={importFile} disabled={busy}
        ><Icon name="upload" size={15} />{t("library.import")}</button
      >
    {/if}
    <input
      type="text"
      bind:value={link}
      placeholder={t("library.playlistPlaceholder")}
      onkeydown={(e) => e.key === "Enter" && addPlaylist()}
    />
    <button onclick={addPlaylist} disabled={busy || !link.trim()}
      ><Icon name="link" size={15} />{t("library.addPlaylist")}</button
    >
  </div>
  {#if message}<p class="error">{message}</p>{/if}
</section>

{#if collections.length === 0}
  <p class="muted empty">{t("library.empty")}</p>
{/if}

<ul class="collections">
  {#each collections as collection (collection.id)}
    <li class="card collection" class:open={open === collection.id}>
      <div class="head">
        <button class="ghost expand" onclick={() => toggle(collection.id)}>
          <span class="badge"
            >{t(KIND[collection.kind] ?? "library.kind.folder")}</span
          >
          <strong>{collection.title}</strong>
          <span class="muted"
            >{collection.items} · {collection.synced_at ??
              t("library.neverSynced")}</span
          >
        </button>
        <button
          class="small"
          disabled={busy}
          onclick={() => sync(collection.id)}
          title={t("library.sync")}
          ><Icon name="retry" size={14} />{t("library.sync")}</button
        >
        <button
          class="small ghost"
          disabled={busy}
          onclick={() => remove(collection.id)}
          title={t("library.remove")}
          aria-label={t("library.remove")}
          ><Icon name="trash" size={14} /></button
        >
      </div>
      <p class="muted source" title={collection.source}>{collection.source}</p>
      {#if summary?.id === collection.id}
        <p class="muted summary" role="status" data-testid="sync-summary">
          {t("library.synced")}:
          {#if summary.parts.length === 0}{t("library.sync.none")}{/if}
          {#each summary.parts as [key, count], i (key)}{i > 0
              ? " · "
              : " "}{count}
            {t(SYNC[key] ?? "library.sync.added")}{/each}
        </p>
      {/if}

      {#if open === collection.id}
        <table class="items">
          <thead>
            <tr>
              <th></th>
              <th>{t("library.col.song")}</th>
              <th>{t("library.col.status")}</th>
              <th>{t("library.col.file")}</th>
              <th>{t("library.col.done")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each items as item (item.id)}
              <tr>
                <td>
                  <input
                    type="checkbox"
                    aria-label={item.title}
                    disabled={item.status !== "ready"}
                    checked={selected.has(item.id)}
                    onchange={(e) => pick(item.id, e.currentTarget.checked)}
                  />
                </td>
                <td>
                  <span class="title">{item.title}</span>
                  {#if item.artist}<span class="muted artist"
                      >{item.artist}</span
                    >{/if}
                </td>
                <td>
                  <span class="badge {statusTone(item.status)}"
                    >{t(STATUS[item.status] ?? "library.status.ready")}</span
                  >
                  {#if item.score !== null && item.status === "needs_review"}
                    <span class="muted">
                      {Math.round((item.score ?? 0) * 100)}%</span
                    >
                  {/if}
                </td>
                <td class="file" title={item.input ?? ""}>
                  {item.input ? baseName(item.input) : "—"}
                </td>
                <td>
                  {#each done[item.id] ?? [] as stem (stem)}
                    <span class="badge ok">{stem}</span>
                  {/each}
                </td>
                <td class="actions">
                  {#if collection.kind === "playlist_file"}
                    {#if isTauri()}
                      <button
                        class="small ghost"
                        onclick={() => chooseFile(item)}
                        >{t("library.choose")}</button
                      >
                    {/if}
                    {#if item.status !== "unavailable"}
                      <button
                        class="small ghost"
                        onclick={() => setMatch(item, null)}
                        >{t("library.markUnavailable")}</button
                      >
                    {/if}
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
        <div class="row footer">
          <button
            class="small ghost"
            onclick={selectNew}
            title={t("library.selectNewHint")}>{t("library.selectNew")}</button
          >
          <span class="muted">{t("library.selected")}: {ready.length}</span>
          <button
            class="primary small"
            disabled={ready.length === 0}
            onclick={() => sendToNewJob(ready)}
            ><Icon name="plus" size={14} />{t("library.separate")}</button
          >
        </div>
      {/if}
    </li>
  {/each}
</ul>

{#if usage}
  <section class="card storage" data-testid="storage">
    <h2>{t("library.storage")}</h2>
    <dl>
      <dt>{t("library.storage.library")}</dt>
      <dd>{formatBytes(usage.library_bytes)} ({usage.library_files})</dd>
      <dt>{t("library.storage.reclaimable")}</dt>
      <dd>{formatBytes(usage.reclaimable_bytes)}</dd>
      <dt>{t("library.storage.models")}</dt>
      <dd>{formatBytes(usage.models_bytes)}</dd>
      <dt>{t("library.storage.tmp")}</dt>
      <dd>{formatBytes(usage.tmp_bytes)}</dd>
    </dl>
    <p class="muted">{t("library.storage.hint")}</p>
    <div class="row">
      <button
        disabled={busy || usage.reclaimable_bytes + usage.tmp_bytes === 0}
        onclick={cleanUp}
        ><Icon name="trash" size={14} />{t("library.cleanup")}</button
      >
      {#if freed !== null}<span class="muted"
          >{t("library.freed")} {formatBytes(freed)}</span
        >{/if}
    </div>
  </section>
{/if}

<style>
  .add .row {
    gap: 0.6rem;
    flex-wrap: wrap;
  }

  .add input {
    flex: 1;
    min-width: 220px;
  }

  .add button,
  .collection button,
  .storage button,
  .footer button {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .empty {
    margin: 1.2rem 0;
  }

  .collections {
    list-style: none;
    margin: 1rem 0;
    padding: 0;
    display: grid;
    gap: 0.8rem;
  }

  .collection {
    display: grid;
    gap: 0.4rem;
    min-width: 0;
  }

  .head {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .expand {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    min-width: 0;
    justify-content: flex-start;
    text-align: left;
  }

  .expand strong {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .source {
    margin: 0;
    font-size: 0.78rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .items {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    table-layout: fixed;
  }

  .items th {
    text-align: left;
    color: var(--muted);
    font-weight: 500;
    padding: 0.4rem;
    border-bottom: 1px solid var(--border);
  }

  .items th:first-child {
    width: 2rem;
  }

  .items td {
    padding: 0.4rem;
    border-bottom: 1px solid var(--border);
    vertical-align: middle;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .items .title,
  .items .artist {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .items .artist {
    font-size: 0.8em;
  }

  .file {
    white-space: nowrap;
  }

  .actions {
    text-align: right;
    white-space: nowrap;
  }

  .footer {
    justify-content: flex-end;
    gap: 0.8rem;
  }

  .storage {
    display: grid;
    gap: 0.6rem;
  }

  .storage h2 {
    margin: 0;
    font-size: 1rem;
  }

  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.3rem 1.2rem;
    margin: 0;
  }

  dt {
    color: var(--muted);
  }

  dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }

  .storage p {
    margin: 0;
    font-size: 0.85rem;
  }
</style>
