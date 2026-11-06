<script lang="ts">
  import type { Schemas } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import { connection, isTauri } from "$lib/connection.svelte";
  import { i18n, t } from "$lib/i18n.svelte";
  import { formatBytes } from "$lib/library";

  let { onchange = () => {} }: { onchange?: () => void } = $props();

  let listing = $state<Schemas["TemporaryOut"] | null>(null);
  // The entries shown for confirmation: exactly what "Delete" removes.
  let confirming = $state(false);
  let busy = $state(false);
  let message = $state("");

  async function load() {
    if (!connection.api) return;
    const { data } = await connection.api.GET("/storage/temporary");
    listing = data ?? null;
  }

  async function review() {
    message = "";
    await load();
    confirming = (listing?.entries.length ?? 0) > 0;
  }

  async function clear() {
    if (!connection.api) return;
    busy = true;
    try {
      const { data, error } = await connection.api.POST(
        "/storage/temporary/clear",
      );
      message = error
        ? t("library.tmp.busy")
        : `${t("library.freed")} ${formatBytes(data?.freed_bytes ?? 0)}`;
    } finally {
      busy = false;
      confirming = false;
      await load();
      onchange();
    }
  }

  async function openFolder() {
    if (!isTauri()) return;
    const { invoke } = await import("@tauri-apps/api/core");
    try {
      await invoke("open_data_folder", { name: "tmp" });
    } catch (err) {
      message = String(err);
    }
  }

  function when(value: string): string {
    return new Date(value).toLocaleString(i18n.locale, {
      dateStyle: "short",
      timeStyle: "short",
    });
  }

  $effect(() => {
    if (connection.status === "ready") void load();
  });
</script>

<section class="card temp" data-testid="temp-files">
  <h2>{t("library.tmp.title")}</h2>
  <p class="muted">{t("library.tmp.hint")}</p>
  {#if listing}
    <p class="folder muted" title={listing.folder}>
      {listing.folder} · {formatBytes(listing.total_bytes)}
    </p>
  {/if}

  {#if confirming && listing}
    <div class="confirm" data-testid="temp-confirm">
      <strong>{t("library.tmp.confirm")}</strong>
      <ul>
        {#each listing.entries as entry (entry.name)}
          <li>
            <code>{entry.name}</code>
            <span class="muted"
              >{formatBytes(entry.bytes)} · {entry.files}
              {t(entry.files === 1 ? "library.tmp.file" : "library.tmp.files")} ·
              {when(entry.modified)}</span
            >
          </li>
        {/each}
      </ul>
      <p class="muted">{t("library.tmp.safe")}</p>
      <div class="row">
        <button class="danger" disabled={busy} onclick={() => void clear()}
          ><Icon name="trash" size={14} />{t("library.tmp.delete")}</button
        >
        <button
          class="ghost"
          disabled={busy}
          onclick={() => (confirming = false)}>{t("library.tmp.cancel")}</button
        >
      </div>
    </div>
  {:else}
    <div class="row">
      <button
        disabled={busy || !listing || listing.entries.length === 0}
        onclick={() => void review()}
        data-testid="temp-review"
        ><Icon name="trash" size={14} />{t("library.tmp.clear")}</button
      >
      {#if isTauri()}
        <button class="ghost" onclick={() => void openFolder()}
          ><Icon name="folder" size={14} />{t("library.tmp.open")}</button
        >
      {/if}
      {#if listing && listing.entries.length === 0}
        <span class="muted">{t("library.tmp.empty")}</span>
      {/if}
    </div>
  {/if}
  {#if message}<p class="muted">{message}</p>{/if}
</section>

<style>
  .temp {
    display: grid;
    gap: 0.6rem;
    margin-top: 1rem;
  }

  h2 {
    margin: 0;
    font-size: 1rem;
  }

  p {
    margin: 0;
    font-size: 0.85rem;
  }

  .folder {
    font-size: 0.8rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .row {
    gap: 0.6rem;
    flex-wrap: wrap;
    align-items: center;
  }

  button {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
  }

  .confirm {
    display: grid;
    gap: 0.5rem;
    padding: 0.8rem;
    border: 1px solid var(--border-strong);
    border-radius: 8px;
  }

  ul {
    margin: 0;
    padding-left: 1.1rem;
    display: grid;
    gap: 0.25rem;
    max-height: 220px;
    overflow: auto;
    font-size: 0.85rem;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }
</style>
