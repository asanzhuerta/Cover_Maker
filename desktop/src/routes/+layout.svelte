<script lang="ts">
  import "../app.css";
  import { onMount, type Snippet } from "svelte";
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import { page } from "$app/state";
  import {
    bootstrap,
    needsSetup,
    startBootstrapWatch,
  } from "$lib/bootstrap.svelte";
  import Icon from "$lib/components/Icon.svelte";
  import Logo from "$lib/components/Logo.svelte";
  import Setup from "$lib/components/Setup.svelte";
  import ShortcutHelp from "$lib/components/ShortcutHelp.svelte";
  import TransportDock from "$lib/components/TransportDock.svelte";
  import { connect, isTauri } from "$lib/connection.svelte";
  import type { IconName } from "$lib/icons";
  import { t, type MessageKey } from "$lib/i18n.svelte";
  import {
    applyInstallerLocale,
    applyTheme,
    settings,
    saveSettings,
  } from "$lib/settings.svelte";
  import { shortcutFor } from "$lib/shortcuts";
  import {
    lanes,
    seekBy,
    selectLane,
    toggle,
    toggleLoop,
    toggleMute,
    toggleOriginal,
    toggleSolo,
    transport,
  } from "$lib/transport.svelte";

  let { children }: { children: Snippet } = $props();

  type Href =
    | "/"
    | "/queue"
    | "/library"
    | "/catalog"
    | "/models"
    | "/settings"
    | "/about";

  const nav: { href: Href; label: MessageKey; icon: IconName }[] = [
    { href: "/", label: "nav.new", icon: "plus" },
    { href: "/queue", label: "nav.queue", icon: "queue" },
    { href: "/library", label: "nav.library", icon: "folder" },
    { href: "/catalog", label: "nav.catalog", icon: "cc" },
    { href: "/models", label: "nav.models", icon: "models" },
  ];
  const navEnd: { href: Href; label: MessageKey; icon: IconName }[] = [
    { href: "/settings", label: "nav.settings", icon: "settings" },
    { href: "/about", label: "nav.about", icon: "info" },
  ];

  let help = $state(false);

  onMount(() => {
    saveSettings();
    applyTheme(settings.theme);
    if (isTauri()) {
      void startBootstrapWatch();
      void applyInstallerLocale();
    }
    void connect();
    if (!settings.welcomed && page.url.pathname !== "/welcome") {
      void goto(resolve("/welcome"));
    }
  });

  const bare = $derived(page.url.pathname === "/welcome");

  function keydown(event: KeyboardEvent) {
    if (bare || help) return;
    const shortcut = shortcutFor(event);
    if (!shortcut) return;
    const loaded = transport.duration > 0;
    const stem = lanes()[transport.selected];
    switch (shortcut.action) {
      case "help":
        help = true;
        break;
      case "play":
        if (!loaded) return;
        void toggle();
        break;
      case "seek":
        if (!loaded) return;
        seekBy(shortcut.seconds);
        break;
      case "loop":
        if (!loaded) return;
        toggleLoop();
        break;
      case "ab":
        if (!loaded) return;
        toggleOriginal();
        break;
      case "lane":
        if (!loaded) return;
        selectLane(shortcut.index);
        break;
      case "laneBy":
        if (!loaded) return;
        selectLane(transport.selected + shortcut.step);
        break;
      case "mute":
        if (!stem) return;
        toggleMute(stem);
        break;
      case "solo":
        if (!stem) return;
        toggleSolo(stem);
        break;
    }
    event.preventDefault();
  }
</script>

<svelte:window onkeydown={keydown} />

{#snippet railLink(item: { href: Href; label: MessageKey; icon: IconName })}
  <li>
    <a
      href={resolve(item.href)}
      class:active={page.url.pathname === item.href}
      aria-current={page.url.pathname === item.href ? "page" : undefined}
      ><Icon name={item.icon} size={20} /><span class="tip"
        >{t(item.label)}</span
      ></a
    >
  </li>
{/snippet}

{#if needsSetup(bootstrap.status)}
  <Setup />
{:else}
  <a class="skip" href="#content">{t("nav.skip")}</a>
  <div class="shell" class:bare>
    {#if !bare}
      <nav class="rail" aria-label={t("nav.label")}>
        <a class="brand" href={resolve("/")} title="Cover_Maker">
          <Logo size={32} />
          <span class="sr-only">Cover_Maker</span>
        </a>
        <ul>
          {#each nav as item (item.href)}{@render railLink(item)}{/each}
        </ul>
        <ul class="end">
          {#each navEnd as item (item.href)}{@render railLink(item)}{/each}
          <li>
            <button
              class="help"
              onclick={() => (help = true)}
              data-testid="shortcuts-button"
              ><span aria-hidden="true">?</span><span class="tip"
                >{t("shortcuts.open")} <kbd>?</kbd></span
              ></button
            >
          </li>
        </ul>
      </nav>
    {/if}
    <main id="content" tabindex="-1">
      {#key page.url.pathname}
        <div class="page" class:reveal={!bare}>
          {@render children()}
        </div>
      {/key}
    </main>
    {#if !bare}<TransportDock />{/if}
  </div>
  <ShortcutHelp bind:open={help} />
{/if}

<style>
  .skip {
    position: absolute;
    left: 0.6rem;
    top: -3rem;
    z-index: 10;
    padding: 0.5rem 0.8rem;
    border-radius: var(--radius-sm);
    background: var(--accent);
    color: var(--accent-fg);
  }

  .skip:focus {
    top: 0.6rem;
  }

  main:focus {
    outline: none;
  }

  .rail {
    position: fixed;
    top: 0;
    left: 0;
    bottom: var(--dock);
    z-index: 6;
    width: var(--rail);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1.1rem;
    padding: 0.9rem 0 0.8rem;
    background: var(--surface);
    border-right: 1px solid var(--border-strong);
  }

  .brand {
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    color: var(--fg);
    border-radius: var(--radius-sm);
  }

  ul {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  ul.end {
    margin-top: auto;
  }

  ul a,
  .help {
    position: relative;
    display: grid;
    place-items: center;
    width: 44px;
    height: 44px;
    padding: 0;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    background: transparent;
    box-shadow: none;
    color: var(--muted);
    text-decoration: none;
    transition:
      background var(--t) ease,
      color var(--t) ease,
      border-color var(--t) ease;
  }

  .help {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: 1rem;
  }

  ul a:hover,
  .help:hover:not(:disabled) {
    background: var(--surface-2);
    color: var(--fg);
    border-color: var(--border);
  }

  ul a.active {
    background: var(--surface-2);
    color: var(--accent-ink);
    border-color: var(--border-strong);
  }

  /* The active page is marked like a lit channel: an orange bar on the edge. */
  ul a.active::before {
    content: "";
    position: absolute;
    left: -11px;
    top: 10px;
    bottom: 10px;
    width: 3px;
    border-radius: 0 2px 2px 0;
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
  }

  /* Names appear on hover and on keyboard focus. */
  .tip {
    position: absolute;
    left: calc(100% + 12px);
    top: 50%;
    z-index: 8;
    padding: 0.3rem 0.6rem;
    border-radius: var(--radius-sm);
    background: var(--fg);
    color: var(--bg);
    font-family: var(--font-display);
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    white-space: nowrap;
    opacity: 0;
    pointer-events: none;
    transform: translate(-4px, -50%);
    transition:
      opacity var(--t) ease,
      transform var(--t) var(--ease-out);
  }

  .tip kbd {
    background: transparent;
    border-color: color-mix(in srgb, var(--bg) 40%, transparent);
    color: inherit;
    min-width: 0;
    padding: 0 0.3rem;
    margin-left: 0.3rem;
  }

  ul a:hover .tip,
  ul a:focus-visible .tip,
  .help:hover .tip,
  .help:focus-visible .tip {
    opacity: 1;
    transform: translate(0, -50%);
  }

  main {
    margin-left: var(--rail);
    padding: 2rem 2.4rem calc(var(--dock) + 2.5rem);
    min-height: 100vh;
  }

  .page {
    max-width: 1180px;
    margin: 0 auto;
  }

  .bare main {
    margin-left: 0;
    padding: 0;
  }

  .bare .page {
    max-width: none;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
</style>
