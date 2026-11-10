<script lang="ts">
  import { onDestroy } from "svelte";
  import { resolve } from "$app/paths";
  import type { Schemas } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import Waveform from "$lib/components/Waveform.svelte";
  import { connection, isTauri, onEvent } from "$lib/connection.svelte";
  import { errorHint } from "$lib/errors";
  import { t, type MessageKey } from "$lib/i18n.svelte";
  import type { IconName } from "$lib/icons";
  import {
    applyEvent,
    itemLabel,
    itemProgress,
    revealTarget,
    stepName,
    type ItemView,
  } from "$lib/jobs";
  import { stemColor } from "$lib/stems";

  type Job = Schemas["JobOut"];

  let jobs = $state<Job[]>([]);
  let items = $state<Record<number, ItemView[]>>({});
  let revealErrors = $state<Record<number, string>>({});
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
      title: item.title ?? null,
      artist: item.artist ?? null,
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

  // Revealing in Explorer needs no path scope and never runs the file
  // (unlike openPath), so any output folder the user picked works.
  async function openFolder(job: Job) {
    const { revealItemInDir } = await import("@tauri-apps/plugin-opener");
    try {
      revealErrors = { ...revealErrors, [job.id]: "" };
      await revealItemInDir(revealTarget(job.output_dir, items[job.id] ?? []));
    } catch (error) {
      revealErrors = {
        ...revealErrors,
        [job.id]: `${t("queue.openFailed")} ${String(error)}`,
      };
    }
  }

  function statusKey(status: string): MessageKey {
    return `status.${status}` as MessageKey;
  }

  function stepLabel(item: ItemView): string {
    if (!item.step) return t(statusKey(item.status));
    const name = stepName(item.step);
    return name ? t(`step.${name}`) : item.step;
  }

  const tone: Record<string, string> = {
    done: "ok",
    failed: "danger",
    cancelled: "warn",
    running: "accent",
  };

  const modeIcon: Record<string, IconName> = {
    extract: "scissors",
    without: "mix",
    both: "download",
  };
</script>

<header class="page-head">
  <div>
    <h1>{t("queue.title")}</h1>
    <p>{t("queue.subtitle")}</p>
  </div>
</header>

{#if jobs.length === 0}
  <div class="card empty">
    <Waveform seed="empty-queue" bars={40} height={40} progress={0} />
    <p class="muted">{t("queue.empty")}</p>
  </div>
{/if}

<ul class="jobs">
  {#each jobs as job (job.id)}
    {@const color = stemColor(job.stems[0] ?? "other")}
    <li class="card job {job.status}" style="--job: {color}" data-testid="job">
      <div class="head">
        <span class="mode-icon" title={t(`new.mode.${job.mode}`)}
          ><Icon name={modeIcon[job.mode] ?? "scissors"} size={18} /></span
        >
        <div class="title">
          <div class="row">
            <strong>#{job.id}</strong>
            <span class="muted">{t(`new.mode.${job.mode}`)}</span>
            <span class="badge {tone[job.status] ?? ''}"
              >{t(statusKey(job.status))}</span
            >
          </div>
          <div class="row tags">
            {#each job.stems as stem (stem)}
              <span class="stem-tag" style="--stem: {stemColor(stem)}"
                ><Icon name={stem} size={12} />{t(`stem.${stem}`)}</span
              >
            {/each}
            <span class="badge">{t(`preset.${job.preset as "fast"}`)}</span>
            <span class="muted count">{job.done}/{job.items}</span>
          </div>
        </div>
        <span class="spacer"></span>
        <div class="row actions">
          {#if job.status === "running" || job.status === "pending"}
            <button class="small" onclick={() => action(job, "pause")}
              ><Icon name="pause" size={14} />{t("queue.pause")}</button
            >
            <button class="small" onclick={() => action(job, "cancel")}
              ><Icon name="x" size={14} />{t("queue.cancel")}</button
            >
          {:else if job.status === "paused"}
            <button class="small" onclick={() => action(job, "resume")}
              ><Icon name="play" size={14} />{t("queue.resume")}</button
            >
          {:else if job.status === "failed" || job.status === "cancelled"}
            <button class="small" onclick={() => action(job, "retry")}
              ><Icon name="retry" size={14} />{t("queue.retry")}</button
            >
          {/if}
          {#if isTauri()}
            <button
              class="small"
              onclick={() => openFolder(job)}
              data-testid="open-folder"
              ><Icon name="folder" size={14} />{t("queue.open")}</button
            >
          {/if}
        </div>
      </div>
      {#if revealErrors[job.id]}
        <p class="error reveal-error">{revealErrors[job.id]}</p>
      {/if}
      <ul class="items">
        {#each items[job.id] ?? [] as item (item.id)}
          {@const progress = itemProgress(item)}
          {@const label = itemLabel(item)}
          <li class={item.status}>
            <div class="name" title={item.input}>
              {#if item.status === "done"}<span class="ok-mark"
                  ><Icon name="check" size={12} strokeWidth={3} /></span
                >{/if}
              <span class="label">
                <span class="title">{label.title}</span>
                {#if label.artist}<span class="artist">{label.artist}</span
                  >{/if}
              </span>
            </div>
            <Waveform
              seed={item.input}
              bars={56}
              height={26}
              {progress}
              {color}
              live={item.status === "running"}
            />
            <div class="state">
              <span class="step">{stepLabel(item)}</span>
              {#if item.status === "done"}
                <a
                  class="mixer-link"
                  href={resolve("/mixer/[item]", { item: String(item.id) })}
                  data-testid="open-mixer"
                  ><Icon name="mix" size={13} />{t("queue.mixer")}</a
                >
              {:else}
                <span class="pct">{Math.round(progress * 100)}%</span>
              {/if}
            </div>
            {#if item.error}
              {@const hint = errorHint(item.error)}
              <div class="error item-error" role="alert">
                {item.error}
                {#if hint}<p class="hint">{t(hint)}</p>{/if}
              </div>
            {/if}
          </li>
        {/each}
      </ul>
    </li>
  {/each}
</ul>

<style>
  .empty {
    display: grid;
    gap: 0.6rem;
    justify-items: center;
    padding: 2rem;
    opacity: 0.9;
  }

  .empty p {
    margin: 0;
  }

  .jobs {
    display: grid;
    gap: 0.9rem;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .job {
    position: relative;
    overflow: hidden;
    padding-left: 1.45rem;
  }

  .job::before {
    content: "";
    position: absolute;
    inset: 0 auto 0 0;
    width: 4px;
    background: var(--job);
    opacity: 0.85;
  }

  .job.running {
    border-color: color-mix(in srgb, var(--job) 45%, var(--border));
    box-shadow:
      var(--shadow),
      0 0 32px color-mix(in srgb, var(--job) 14%, transparent);
  }

  .head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.8rem;
  }

  .mode-icon {
    display: grid;
    place-items: center;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    border: 1px solid var(--border);
    color: color-mix(in oklab, var(--job), var(--fg) var(--stem-ink-mix));
    background: color-mix(in srgb, var(--job) 14%, transparent);
  }

  .title {
    display: grid;
    gap: 0.35rem;
  }

  .tags {
    gap: 0.3rem;
  }

  .count {
    font-size: 0.8rem;
    font-variant-numeric: tabular-nums;
  }

  .spacer {
    flex: 1;
  }

  .actions {
    gap: 0.35rem;
  }

  .reveal-error {
    margin: 0.6rem 0 0;
    font-size: 0.85rem;
  }

  .items {
    display: grid;
    gap: 0.35rem;
    padding: 0;
    margin: 1rem 0 0;
    list-style: none;
  }

  .items li {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(0, 1.2fr) 150px;
    align-items: center;
    gap: 0.9rem;
    padding: 0.45rem 0.6rem;
    border-radius: var(--radius-sm);
    background: var(--surface);
    border: 1px solid var(--border);
  }

  .name {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    overflow: hidden;
  }

  .label {
    display: grid;
    min-width: 0;
    line-height: 1.25;
  }

  .label .title,
  .label .artist {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .label .artist {
    color: var(--muted);
    font-size: 0.8em;
  }

  .ok-mark {
    display: grid;
    place-items: center;
    flex: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--ok);
    color: var(--bg);
  }

  .state {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: var(--muted);
  }

  .pct {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }

  .mixer-link {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-weight: 600;
    text-decoration: none;
  }

  .running .pct {
    color: var(--job);
  }

  .item-error .hint {
    margin: 0.3rem 0 0;
    color: var(--fg);
    font-size: 0.85em;
  }

  .item-error {
    grid-column: 1 / -1;
    font-size: 0.82rem;
  }
</style>
