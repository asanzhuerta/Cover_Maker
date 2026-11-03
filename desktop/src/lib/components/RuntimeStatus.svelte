<script lang="ts">
  // Live state of the background separation runtime install (phase B), for
  // pages without the sidebar such as the welcome tutorial.
  import { bootstrap, retryBootstrap } from "$lib/bootstrap.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import { t } from "$lib/i18n.svelte";

  const phase = $derived(bootstrap.status.separation);
  const ready = $derived(
    bootstrap.status.mode === "development" || phase.state === "done",
  );
</script>

<div
  class="status card"
  class:ready
  class:failed={phase.state === "failed"}
  data-testid="runtime-status"
>
  {#if ready}
    <span class="icon ok"><Icon name="check" size={16} strokeWidth={3} /></span>
    <div>
      <strong>{t("bootstrap.separationReady")}</strong>
      {#if bootstrap.status.torch}<span class="muted">
          ({bootstrap.status.torch})</span
        >{/if}
      <p class="muted">{t("tour.runtimeReady")}</p>
    </div>
  {:else if phase.state === "failed"}
    <span class="icon"><Icon name="x" size={16} strokeWidth={3} /></span>
    <div>
      <strong>{t("bootstrap.separationFailed")}</strong>
      <p class="muted" title={phase.error}>{t("runtime.failed")}</p>
      <button class="small" onclick={() => void retryBootstrap()}
        >{t("bootstrap.retry")}</button
      >
    </div>
  {:else}
    <span class="spinner"></span>
    <div>
      <strong>{t("bootstrap.separation")}</strong>
      {#if bootstrap.status.torch}<span class="muted">
          ({bootstrap.status.torch})</span
        >{/if}
      <p class="muted">{t("tour.runtimeRunning")}</p>
    </div>
  {/if}
</div>

<style>
  .status {
    display: flex;
    align-items: flex-start;
    gap: 0.8rem;
    border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
  }

  .status.ready {
    border-color: color-mix(in srgb, var(--ok) 45%, var(--border));
  }

  .status.failed {
    border-color: color-mix(in srgb, var(--danger) 45%, var(--border));
  }

  p {
    margin: 0.25rem 0 0;
    font-size: 0.85rem;
  }

  button {
    margin-top: 0.5rem;
  }

  .icon {
    display: grid;
    place-items: center;
    width: 26px;
    height: 26px;
    flex: none;
    border-radius: 50%;
    color: var(--danger);
    background: color-mix(in srgb, var(--danger) 15%, transparent);
  }

  .icon.ok {
    color: var(--ok);
    background: color-mix(in srgb, var(--ok) 15%, transparent);
  }

  .spinner {
    width: 22px;
    height: 22px;
    flex: none;
    margin: 2px;
    border-radius: 50%;
    border: 3px solid var(--border-strong);
    border-top-color: var(--accent);
    animation: spin 0.9s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
