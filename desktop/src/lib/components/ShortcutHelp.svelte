<script lang="ts">
  import { t } from "$lib/i18n.svelte";
  import { SHORTCUT_HELP } from "$lib/shortcuts";

  let { open = $bindable(false) }: { open?: boolean } = $props();

  let dialog = $state<HTMLDialogElement | null>(null);

  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  });
</script>

<dialog
  bind:this={dialog}
  onclose={() => (open = false)}
  aria-labelledby="shortcuts-title"
  data-testid="shortcut-help"
>
  <h3 id="shortcuts-title">{t("shortcuts.title")}</h3>
  <dl>
    {#each SHORTCUT_HELP as row (row.label)}
      <dt>
        {#each row.keys as key, i (i)}{#if key === "–"}<span class="muted">
              –
            </span>{:else}<kbd>{key}</kbd>{/if}{/each}
      </dt>
      <dd>{t(row.label)}</dd>
    {/each}
  </dl>
  <p class="muted">{t("shortcuts.note")}</p>
  <form method="dialog">
    <button class="primary">{t("shortcuts.close")}</button>
  </form>
</dialog>

<style>
  dialog {
    width: min(460px, calc(100vw - 2rem));
    padding: 1.3rem 1.4rem;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius);
    background: var(--surface);
    color: var(--fg);
    box-shadow: 0 24px 60px rgb(0 0 0 / 50%);
  }

  dialog[open] {
    animation: pop 180ms var(--ease-out);
  }

  dialog::backdrop {
    background: rgb(12 11 10 / 60%);
  }

  h3 {
    margin: 0 0 1rem;
  }

  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.55rem 1rem;
    margin: 0;
    align-items: center;
  }

  dt {
    display: flex;
    gap: 0.25rem;
    justify-content: flex-end;
  }

  dd {
    margin: 0;
  }

  p {
    font-size: 0.85rem;
  }

  form {
    display: flex;
    justify-content: flex-end;
  }

  @keyframes pop {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    dialog[open] {
      animation: none;
    }
  }
</style>
