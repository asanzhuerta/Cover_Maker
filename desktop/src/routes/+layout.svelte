<script lang="ts">
  import "../app.css";
  import { onMount, type Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import { page } from "$app/state";
  import { connect, connection } from "$lib/connection.svelte";
  import { t, type MessageKey } from "$lib/i18n.svelte";
  import { applyTheme, settings, saveSettings } from "$lib/settings.svelte";

  let { children }: { children: Snippet } = $props();

  const nav: {
    href: "/" | "/queue" | "/models" | "/settings";
    label: MessageKey;
  }[] = [
    { href: "/", label: "nav.new" },
    { href: "/queue", label: "nav.queue" },
    { href: "/models", label: "nav.models" },
    { href: "/settings", label: "nav.settings" },
  ];

  onMount(() => {
    saveSettings();
    applyTheme(settings.theme);
    void connect();
    if (!settings.welcomed && page.url.pathname !== "/welcome") {
      void goto(resolve("/welcome"));
    }
  });

  const statusLabel = $derived(
    connection.status === "ready"
      ? t("engine.ready")
      : connection.status === "starting"
        ? t("engine.starting")
        : t("engine.offline"),
  );
</script>

<div class="shell">
  <aside>
    <div class="brand">Cover_Maker</div>
    <nav>
      {#each nav as item (item.href)}
        <a
          href={resolve(item.href)}
          class:active={page.url.pathname === item.href}>{t(item.label)}</a
        >
      {/each}
    </nav>
    <div class="engine" data-testid="engine-status" title={connection.error}>
      <span class="dot {connection.status}"></span>
      {statusLabel}
      {#if connection.demo}<span class="badge">{t("engine.demo")}</span>{/if}
    </div>
  </aside>
  <main>
    {@render children()}
  </main>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: 220px 1fr;
    min-height: 100vh;
  }

  aside {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    padding: 1.2rem 0.9rem;
    border-right: 1px solid var(--border);
    background: var(--surface);
  }

  .brand {
    font-weight: 700;
    font-size: 1.15rem;
    color: var(--accent);
    padding: 0 0.5rem;
  }

  nav {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  nav a {
    padding: 0.5rem 0.7rem;
    border-radius: 8px;
    color: var(--fg);
    text-decoration: none;
  }

  nav a:hover {
    background: var(--surface-2);
  }

  nav a.active {
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 600;
  }

  .engine {
    margin-top: auto;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.85rem;
    color: var(--muted);
    padding: 0 0.5rem;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--warn);
  }

  .dot.ready {
    background: var(--ok);
  }

  .dot.offline {
    background: var(--danger);
  }

  main {
    padding: 1.8rem 2.2rem;
    max-width: 1000px;
    width: 100%;
  }
</style>
