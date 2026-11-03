<script lang="ts">
  import "../app.css";
  import { onMount, type Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import { page } from "$app/state";
  import Icon from "$lib/components/Icon.svelte";
  import { connect, connection } from "$lib/connection.svelte";
  import type { IconName } from "$lib/icons";
  import { t, type MessageKey } from "$lib/i18n.svelte";
  import { applyTheme, settings, saveSettings } from "$lib/settings.svelte";

  let { children }: { children: Snippet } = $props();

  const nav: {
    href: "/" | "/queue" | "/models" | "/settings" | "/about";
    label: MessageKey;
    icon: IconName;
  }[] = [
    { href: "/", label: "nav.new", icon: "plus" },
    { href: "/queue", label: "nav.queue", icon: "queue" },
    { href: "/models", label: "nav.models", icon: "models" },
    { href: "/settings", label: "nav.settings", icon: "settings" },
    { href: "/about", label: "nav.about", icon: "info" },
  ];

  const logo = [0.35, 0.7, 1, 0.55, 0.85, 0.4];

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

<div class="shell" class:bare={page.url.pathname === "/welcome"}>
  <aside>
    <div class="brand">
      <svg viewBox="0 0 28 28" width="30" height="30" aria-hidden="true">
        <defs>
          <linearGradient id="logo-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stop-color="#8f7bff" />
            <stop offset="1" stop-color="#ff5c8a" />
          </linearGradient>
        </defs>
        <rect width="28" height="28" rx="8" fill="url(#logo-gradient)" />
        {#each logo as level, i (i)}
          <rect
            x={4.6 + i * 3.4}
            y={14 - level * 8}
            width="2"
            height={level * 16}
            rx="1"
            fill="#fff"
          />
        {/each}
      </svg>
      <span>Cover<span class="muted">_</span>Maker</span>
    </div>
    <nav>
      {#each nav as item (item.href)}
        <a
          href={resolve(item.href)}
          class:active={page.url.pathname === item.href}
          ><Icon name={item.icon} />{t(item.label)}</a
        >
      {/each}
    </nav>
    <div
      class="engine {connection.status}"
      data-testid="engine-status"
      title={connection.error}
    >
      <span class="dot"></span>
      <span>{statusLabel}</span>
      {#if connection.demo}<span class="badge accent">{t("engine.demo")}</span
        >{/if}
    </div>
  </aside>
  <main>
    {@render children()}
  </main>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: 232px 1fr;
    min-height: 100vh;
  }

  aside {
    position: sticky;
    top: 0;
    height: 100vh;
    display: flex;
    flex-direction: column;
    gap: 1.8rem;
    padding: 1.3rem 0.9rem;
    border-right: 1px solid var(--border);
    background: color-mix(in srgb, var(--surface) 82%, transparent);
    backdrop-filter: blur(12px);
  }

  .bare aside {
    display: none;
  }

  .bare {
    grid-template-columns: 1fr;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1.1rem;
    padding: 0 0.4rem;
  }

  nav {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  nav a {
    position: relative;
    display: flex;
    align-items: center;
    gap: 0.7rem;
    padding: 0.6rem 0.75rem;
    border-radius: 10px;
    color: var(--muted);
    text-decoration: none;
    font-weight: 500;
    transition:
      background 0.15s ease,
      color 0.15s ease;
  }

  nav a:hover {
    background: var(--surface-2);
    color: var(--fg);
  }

  nav a.active {
    background: var(--accent-soft);
    color: var(--fg);
    font-weight: 600;
  }

  nav a.active::before {
    content: "";
    position: absolute;
    left: -0.9rem;
    top: 22%;
    bottom: 22%;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: var(--gradient);
  }

  nav a.active :global(.icon) {
    color: var(--accent);
  }

  .engine {
    margin-top: auto;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
    color: var(--muted);
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 12px;
    background: var(--surface-2);
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--warn);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--warn) 22%, transparent);
  }

  .ready .dot {
    background: var(--ok);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--ok) 22%, transparent);
  }

  .offline .dot {
    background: var(--danger);
    box-shadow: 0 0 0 3px color-mix(in srgb, var(--danger) 22%, transparent);
  }

  main {
    padding: 2rem 2.4rem 3rem;
    max-width: 1040px;
    width: 100%;
  }

  .bare main {
    max-width: none;
    padding: 0;
  }
</style>
