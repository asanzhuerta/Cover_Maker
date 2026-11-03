<script lang="ts">
  import { bootstrap, separationReady } from "$lib/bootstrap.svelte";
  import { t } from "$lib/i18n.svelte";

  const state = $derived(bootstrap.status.separation.state);
</script>

{#if !separationReady(bootstrap.status)}
  <p
    class="notice"
    class:failed={state === "failed"}
    data-testid="runtime-notice"
  >
    {state === "failed" ? t("runtime.failed") : t("runtime.wait")}
  </p>
{/if}

<style>
  .notice {
    margin: 0 0 1rem;
    padding: 0.7rem 0.9rem;
    border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--warn) 45%, transparent);
    background: color-mix(in srgb, var(--warn) 10%, transparent);
    font-size: 0.85rem;
  }

  .notice.failed {
    border-color: color-mix(in srgb, var(--danger) 45%, transparent);
    background: color-mix(in srgb, var(--danger) 10%, transparent);
  }
</style>
