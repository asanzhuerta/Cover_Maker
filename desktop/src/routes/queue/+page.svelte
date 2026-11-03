<script lang="ts">
  import { onDestroy } from "svelte";
  import type { Schemas } from "$lib/api/client";
  import { connection, isTauri, onEvent } from "$lib/connection.svelte";
  import { t, type MessageKey } from "$lib/i18n.svelte";
  import {
    applyEvent,
    displayName,
    itemProgress,
    type ItemView,
  } from "$lib/jobs";

  type Job = Schemas["JobOut"];

  let jobs = $state<Job[]>([]);
  let items = $state<Record<number, ItemView[]>>({});
  let reloading = false;

  async function loadJob(id: number) {
    if (!connection.api) return;
    const { data } = await connection.api.GET("/jobs/{job_id}", {
      params: { path: { job_id: id } },
    });
    if (!data) return;
    items[id] = data.item_list.map((item) => ({
      id: item.id,
      input: item.input,
      status: item.status,
      step: item.current_step ?? null,
      fraction: null,
      error: item.error ?? null,
      outputs: item.outputs,
    }));
  }

  async function load() {
    if (!connection.api || reloading) return;
    reloading = true;
    const { data } = await connection.api.GET("/jobs", {
      params: { query: { limit: 30 } },
    });
    reloading = false;
    if (!data) return;
    jobs = data;
    await Promise.all(data.map((job) => loadJob(job.id)));
  }

  $effect(() => {
    if (connection.status === "ready") void load();
  });

  const stop = onEvent((event) => {
    const jobId = event.job as number | undefined;
    if (event.type === "job.submitted" || event.type === "job.finished") {
      void load();
      return;
    }
    if (jobId !== undefined && items[jobId])
      items[jobId] = applyEvent(items[jobId], event);
  });
  onDestroy(stop);

  async function action(
    job: Job,
    kind: "cancel" | "pause" | "resume" | "retry",
  ) {
    if (!connection.api) return;
    const params = { params: { path: { job_id: job.id } } };
    if (kind === "cancel")
      await connection.api.POST("/jobs/{job_id}/cancel", params);
    if (kind === "pause")
      await connection.api.POST("/jobs/{job_id}/pause", params);
    if (kind === "resume")
      await connection.api.POST("/jobs/{job_id}/resume", params);
    if (kind === "retry")
      await connection.api.POST("/jobs/{job_id}/retry", params);
    await load();
  }

  async function openFolder(path: string) {
    const { openPath } = await import("@tauri-apps/plugin-opener");
    await openPath(path);
  }

  function statusKey(status: string): MessageKey {
    return `status.${status}` as MessageKey;
  }

  const tone: Record<string, string> = {
    done: "ok",
    failed: "danger",
    cancelled: "warn",
  };
</script>

<h1>{t("queue.title")}</h1>

{#if jobs.length === 0}
  <p class="muted">{t("queue.empty")}</p>
{/if}

<ul class="jobs">
  {#each jobs as job (job.id)}
    <li class="card" data-testid="job">
      <div class="head">
        <strong>#{job.id}</strong>
        <span class="badge {tone[job.status] ?? ''}"
          >{t(statusKey(job.status))}</span
        >
        <span class="muted">
          {job.mode === "without"
            ? t("new.mode.without")
            : t("new.mode.extract")}:
          {job.stems.map((s) => t(`stem.${s}`)).join(", ")} · {t(
            `preset.${job.preset as "fast"}`,
          )}
        </span>
        <span class="spacer"></span>
        {#if job.status === "running" || job.status === "pending"}
          <button onclick={() => action(job, "pause")}
            >{t("queue.pause")}</button
          >
          <button onclick={() => action(job, "cancel")}
            >{t("queue.cancel")}</button
          >
        {:else if job.status === "paused"}
          <button onclick={() => action(job, "resume")}
            >{t("queue.resume")}</button
          >
        {:else if job.status === "failed" || job.status === "cancelled"}
          <button onclick={() => action(job, "retry")}
            >{t("queue.retry")}</button
          >
        {/if}
        {#if isTauri()}
          <button onclick={() => openFolder(job.output_dir)}
            >{t("queue.open")}</button
          >
        {/if}
      </div>
      <ul class="items">
        {#each items[job.id] ?? [] as item (item.id)}
          <li>
            <div class="name" title={item.input}>{displayName(item.input)}</div>
            <div class="progress">
              <div style="width: {itemProgress(item) * 100}%"></div>
            </div>
            <div class="state muted">
              {item.step ?? t(statusKey(item.status))}
              {#if item.error}<span class="error">{item.error}</span>{/if}
            </div>
          </li>
        {/each}
      </ul>
    </li>
  {/each}
</ul>

<style>
  .jobs {
    display: grid;
    gap: 0.9rem;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
  }

  .spacer {
    flex: 1;
  }

  .items {
    display: grid;
    gap: 0.6rem;
    padding: 0;
    margin: 0.9rem 0 0;
    list-style: none;
  }

  .items li {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) 1fr minmax(0, 1fr);
    align-items: center;
    gap: 0.8rem;
  }

  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .state {
    font-size: 0.85rem;
    display: grid;
  }
</style>
