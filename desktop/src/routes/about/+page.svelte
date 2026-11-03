<script lang="ts">
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import { about, contactLinks, localized } from "$lib/about";
  import Icon from "$lib/components/Icon.svelte";
  import { isTauri } from "$lib/connection.svelte";
  import { i18n, t } from "$lib/i18n.svelte";

  const author = about.author;
  const links = contactLinks(author);

  // External pages and mail in the system handlers (opener:default scope).
  async function open(url: string) {
    if (!isTauri()) {
      window.open(url, "_blank", "noopener,noreferrer");
      return;
    }
    const { openUrl } = await import("@tauri-apps/plugin-opener");
    await openUrl(url);
  }
</script>

<header class="page-head">
  <div>
    <h1>{t("about.title")}</h1>
    <p>{t("about.subtitle")}</p>
  </div>
</header>

<div class="grid">
  <section class="card profile" data-testid="about-profile">
    <img src={author.photo} alt={t("about.photo")} width="96" height="96" />
    <div class="who">
      <p class="kicker">{t("about.author")}</p>
      <h2>{author.name}</h2>
      <p class="muted">{localized(author.bio, i18n.locale)}</p>
      <ul class="links">
        {#each links as link (link.kind)}
          <li>
            <button class="ghost small" onclick={() => void open(link.href)}>
              <Icon name="external" />
              <span class="kind">{t(`about.link.${link.kind}`)}</span>
              <span class="muted">{link.label}</span>
            </button>
          </li>
        {/each}
      </ul>
    </div>
  </section>

  <section class="card app">
    <p class="kicker">{t("about.app")}</p>
    <h2>
      <span class="gradient-text">Cover_Maker</span>
    </h2>
    <p>{localized(about.app.description, i18n.locale)}</p>
    <button class="ghost small" onclick={() => void open(about.app.repository)}
      ><Icon name="external" />{t("about.source")}</button
    >
  </section>

  <section class="card credits" data-testid="about-credits">
    <p class="kicker">{t("about.credits")}</p>
    <p class="muted">{t("about.creditsIntro")}</p>
    <ul>
      {#each about.credits as credit (credit.name)}
        <li>
          <button class="link" onclick={() => void open(credit.url)}
            >{credit.name}</button
          >
          <span class="muted">{localized(credit.role, i18n.locale)}</span>
          <span class="badge">{credit.licence}</span>
        </li>
      {/each}
    </ul>
    <div class="row">
      <button class="small" onclick={() => void open(about.notices)}
        ><Icon name="external" />{t("about.notices")}</button
      >
      <button class="small" onclick={() => void goto(resolve("/models"))}
        ><Icon name="models" />{t("about.modelLicences")}</button
      >
    </div>
  </section>
</div>

<style>
  .grid {
    display: grid;
    gap: 1.2rem;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    max-width: 1000px;
    /* Size from the page, not from the content, so the grid never widens main. */
    container-type: inline-size;
  }

  .card {
    display: grid;
    gap: 0.7rem;
    align-content: start;
  }

  .credits {
    grid-column: 1 / -1;
  }

  .kicker {
    margin: 0;
    color: var(--accent);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.72rem;
  }

  h2 {
    margin: 0;
    font-family: var(--font-display);
  }

  p {
    margin: 0;
  }

  .profile {
    grid-template-columns: auto 1fr;
    gap: 1.2rem;
  }

  .profile img {
    border-radius: 50%;
    box-shadow: 0 0 0 3px var(--accent-soft);
  }

  .who {
    display: grid;
    gap: 0.5rem;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .links {
    display: grid;
    gap: 0.3rem;
    justify-items: start;
  }

  .links button {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    max-width: 100%;
    text-align: left;
    overflow-wrap: anywhere;
    min-width: 0;
  }

  .kind {
    font-weight: 600;
    white-space: nowrap;
  }

  .app button {
    justify-self: start;
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }

  .credits ul {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.5rem 1.2rem;
  }

  .credits li {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0.45rem 0;
    border-bottom: 1px solid var(--border);
  }

  button.link {
    padding: 0;
    border: 0;
    background: none;
    color: var(--fg);
    font-weight: 600;
    text-decoration: underline;
    text-decoration-color: var(--border-strong);
    text-underline-offset: 3px;
  }

  .credits .badge {
    margin-left: auto;
  }

  .credits .row {
    gap: 0.6rem;
  }

  .credits .row button {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
  }
</style>
