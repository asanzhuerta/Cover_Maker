<script lang="ts">
  import {
    bootstrap,
    phaseProgress,
    retryBootstrap,
    stepLabel,
  } from "$lib/bootstrap.svelte";
  import { t } from "$lib/i18n.svelte";
  import { formatBytes } from "$lib/library";
  import { runtimeFits } from "$lib/space";

  const core = $derived(bootstrap.status.core);
  const progress = $derived(phaseProgress(core));
  const space = $derived(bootstrap.status.space ?? null);
  const fits = $derived(space === null || runtimeFits(space));
  const consent = $derived(core.state === "consent");
  const steps = ["python", "venv", "engine", "ffmpeg", "deno"];
  let starting = $state(false);

  async function start() {
    starting = true;
    try {
      await retryBootstrap();
    } finally {
      starting = false;
    }
  }
</script>

<section class="setup" data-testid="setup">
  <div class="card panel">
    <p class="kicker">{t("bootstrap.kicker")}</p>
    <h1><span class="gradient-text">{t("bootstrap.title")}</span></h1>
    <p class="muted">
      {consent ? t("bootstrap.space.intro") : t("bootstrap.intro")}
    </p>

    {#if space}
      <dl class="space" data-testid="setup-space">
        <dt>{t("bootstrap.space.download")}</dt>
        <dd>{formatBytes(space.download_bytes)}</dd>
        <dt>{t("bootstrap.space.disk")}</dt>
        <dd>~{formatBytes(space.disk_bytes)}</dd>
        <dt>{t("bootstrap.space.free")}</dt>
        <dd class:short={!fits}>
          {space.free_bytes === null ? "?" : formatBytes(space.free_bytes)}
        </dd>
        <dt>{t("bootstrap.space.build")}</dt>
        <dd>
          {space.torch === "cu128"
            ? t("bootstrap.space.torch.cu128")
            : t("bootstrap.space.torch.cpu")}
        </dd>
        <dt>{t("bootstrap.space.folder")}</dt>
        <dd class="folder" title={space.folder}>{space.folder}</dd>
      </dl>
      <p class="muted note">{t("bootstrap.space.models")}</p>
      {#if !fits}
        <p class="short" data-testid="setup-short">
          {t("bootstrap.space.short")}
        </p>
      {/if}
    {/if}

    {#if consent}
      <button
        class="primary start"
        data-testid="setup-start"
        disabled={starting}
        onclick={() => void start()}
        >{fits ? t("bootstrap.start") : t("bootstrap.recheck")}</button
      >
    {:else}
      <ol>
        {#each steps as step, i (step)}
          {@const key = stepLabel(step)}
          <li
            class:active={core.state !== "done" && core.index === i + 1}
            class:finished={core.index > i + 1}
          >
            <span class="dot"></span>{key ? t(key) : step}
          </li>
        {/each}
      </ol>

      <div class="bar" aria-hidden="true">
        <span
          class:indeterminate={progress === null}
          style:width="{Math.round((progress ?? 0.3) * 100)}%"
        ></span>
      </div>
      <p class="detail muted" title={core.detail}>{core.detail || "…"}</p>
    {/if}

    {#if core.state === "failed"}
      <div class="error">
        <strong>{t("bootstrap.failed")}</strong>
        <code>{core.error}</code>
        <button class="primary" onclick={() => void retryBootstrap()}
          >{t("bootstrap.retry")}</button
        >
      </div>
    {/if}
  </div>
</section>

<style>
  .setup {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 2rem;
  }

  .panel {
    width: min(560px, 100%);
    display: grid;
    gap: 1rem;
  }

  .kicker {
    margin: 0;
    color: var(--accent);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.75rem;
  }

  h1 {
    margin: 0;
    font-family: var(--font-display);
  }

  ol {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.45rem;
  }

  li {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    color: var(--muted);
  }

  li.active {
    color: var(--fg);
    font-weight: 600;
  }

  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--border-strong);
  }

  li.active .dot {
    background: var(--accent);
  }

  li.finished .dot {
    background: var(--ok);
  }

  .bar {
    height: 6px;
    border-radius: 3px;
    background: var(--border);
    overflow: hidden;
  }

  .bar span {
    display: block;
    height: 100%;
    background: var(--gradient);
    transition: width 0.3s ease;
  }

  .bar span.indeterminate {
    animation: slide 1.4s ease-in-out infinite;
  }

  @keyframes slide {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(340%);
    }
  }

  .detail {
    margin: 0;
    font-size: 0.8rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .error {
    display: grid;
    gap: 0.5rem;
    color: var(--danger);
  }

  .error code {
    white-space: pre-wrap;
    font-size: 0.8rem;
    color: var(--fg);
  }

  .error button {
    justify-self: start;
  }

  .space {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.35rem 1rem;
    margin: 0;
    font-size: 0.9rem;
  }

  .space dt {
    color: var(--muted);
  }

  .space dd {
    margin: 0;
    font-variant-numeric: tabular-nums;
  }

  .space .folder {
    font-size: 0.8rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .note {
    margin: 0;
    font-size: 0.82rem;
  }

  .short {
    color: var(--danger);
    font-weight: 600;
    margin: 0;
  }

  .start {
    justify-self: start;
  }
</style>
