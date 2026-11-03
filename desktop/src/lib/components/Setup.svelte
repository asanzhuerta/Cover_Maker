<script lang="ts">
  import {
    bootstrap,
    phaseProgress,
    retryBootstrap,
    stepLabel,
  } from "$lib/bootstrap.svelte";
  import { t } from "$lib/i18n.svelte";

  const core = $derived(bootstrap.status.core);
  const progress = $derived(phaseProgress(core));
  const steps = ["python", "venv", "engine", "ffmpeg", "deno"];
</script>

<section class="setup" data-testid="setup">
  <div class="card panel">
    <p class="kicker">{t("bootstrap.kicker")}</p>
    <h1><span class="gradient-text">{t("bootstrap.title")}</span></h1>
    <p class="muted">{t("bootstrap.intro")}</p>

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
</style>
