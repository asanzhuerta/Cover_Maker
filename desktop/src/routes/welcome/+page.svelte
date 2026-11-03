<script lang="ts">
  import { goto } from "$app/navigation";
  import { resolve } from "$app/paths";
  import type { Schemas } from "$lib/api/client";
  import Icon from "$lib/components/Icon.svelte";
  import ModelPreview from "$lib/components/ModelPreview.svelte";
  import RuntimeStatus from "$lib/components/RuntimeStatus.svelte";
  import Waveform from "$lib/components/Waveform.svelte";
  import { connection } from "$lib/connection.svelte";
  import { t, type MessageKey } from "$lib/i18n.svelte";
  import { saveSettings, settings } from "$lib/settings.svelte";
  import { STEM_COLORS, STEMS } from "$lib/stems";

  const STEPS: MessageKey[] = [
    "welcome.step.terms",
    "welcome.step.engine",
    "welcome.step.models",
  ];

  let accepted = $state(settings.welcomed);
  let step = $state(0);
  let system = $state<Schemas["SystemOut"] | null>(null);

  $effect(() => {
    if (connection.status === "ready" && connection.api && !system) {
      void connection.api
        .GET("/system")
        .then(({ data }) => (system = data ?? null));
    }
  });

  const canNext = $derived(step > 0 || accepted);

  function finish() {
    settings.welcomed = true;
    saveSettings();
    void goto(resolve("/"));
  }
</script>

<div class="welcome">
  <section class="hero">
    <div class="hero-text">
      <span class="badge accent">{t("welcome.kicker")}</span>
      <h1>
        {t("welcome.title")}
        <span class="gradient-text">Cover_Maker</span>
      </h1>
      <p class="intro">{t("welcome.intro")}</p>
    </div>
    <div class="lanes" aria-hidden="true">
      {#each STEMS as stem, i (stem)}
        <div class="lane" style="--stem: {STEM_COLORS[stem]}">
          <span class="lane-icon"><Icon name={stem} size={16} /></span>
          <span class="lane-name">{t(`stem.${stem}`)}</span>
          <Waveform
            seed={`hero-${stem}`}
            bars={44}
            height={26}
            progress={1 - i * 0.12}
            color={STEM_COLORS[stem]}
          />
        </div>
      {/each}
    </div>
  </section>

  <ol class="steps" data-testid="welcome-steps">
    {#each STEPS as label, i (label)}
      <li class:done={i < step} class:current={i === step}>
        <span class="num"
          >{#if i < step}<Icon
              name="check"
              size={14}
              strokeWidth={3}
            />{:else}{i + 1}{/if}</span
        >
        <span>{t(label)}</span>
      </li>
    {/each}
  </ol>

  <section class="panel">
    {#if step === 0}
      <div class="card legal">
        <span class="legal-icon"><Icon name="shield" size={22} /></span>
        <div>
          <h3>{t("welcome.step.terms")}</h3>
          <p>{t("welcome.legal")}</p>
          <label class="row accept">
            <input
              type="checkbox"
              bind:checked={accepted}
              data-testid="accept-terms"
            />
            {t("welcome.accept")}
          </label>
        </div>
      </div>
    {:else if step === 1}
      <h3>{t("tour.engineTitle")}</h3>
      <p class="lead">{t("tour.engineIntro")}</p>
      <RuntimeStatus />
      <p class="muted">{t("tour.engineSidebar")}</p>
      <h4>{t("welcome.hardware")}</h4>
      {#if system}
        <div class="hw">
          <div class="card tile">
            <span class="tile-icon"><Icon name="cpu" size={20} /></span>
            <span class="muted">CPU</span>
            <strong>{system.cpu}</strong>
          </div>
          <div class="card tile">
            <span class="tile-icon"><Icon name="ram" size={20} /></span>
            <span class="muted">RAM</span>
            <strong>{system.ram_gb} GB</strong>
          </div>
          <div class="card tile">
            <span class="tile-icon"><Icon name="gpu" size={20} /></span>
            <span class="muted">GPU</span>
            {#if system.gpu}
              <strong>{system.gpu.name}</strong>
              <span class="muted">{system.gpu.total_mb} MB VRAM</span>
            {:else}
              <strong>{t("hw.cpuOnly")}</strong>
            {/if}
          </div>
          <div class="card tile highlight">
            <span class="tile-icon"><Icon name="mix" size={20} /></span>
            <span class="muted">{t("hw.preset")}</span>
            <strong class="gradient-text big"
              >{t(`preset.${system.recommended_preset as "fast"}`)}</strong
            >
            <span class="muted">{t("hw.tier")}: {system.tier}</span>
          </div>
        </div>
      {:else}
        <p class="muted">{t("tour.scanning")}</p>
      {/if}
    {:else}
      <h3>{t("welcome.models")}</h3>
      <p class="lead">{t("tour.modelsIntro")}</p>
      <ModelPreview />
      <h4>{t("tour.nextTitle")}</h4>
      <ol class="next">
        <li>{t("tour.next1")}</li>
        <li>{t("tour.next2")}</li>
        <li>{t("tour.next3")}</li>
      </ol>
    {/if}

    <div class="row nav">
      {#if step > 0}
        <button class="ghost" onclick={() => (step -= 1)}
          ><Icon name="arrowLeft" size={16} />{t("welcome.back")}</button
        >
      {/if}
      <span class="spacer"></span>
      {#if step < STEPS.length - 1}
        <button
          class="primary"
          disabled={!canNext}
          onclick={() => (step += 1)}
          data-testid="welcome-next"
          >{t("welcome.next")}<Icon name="arrowRight" size={16} /></button
        >
      {:else}
        <button class="ghost" onclick={finish}>{t("welcome.skip")}</button>
        <button class="primary" onclick={finish} data-testid="welcome-finish"
          >{t("welcome.finish")}<Icon name="arrowRight" size={16} /></button
        >
      {/if}
    </div>
  </section>
</div>

<style>
  .welcome {
    max-width: 1040px;
    margin: 0 auto;
    padding: 2.5rem 2.4rem 3rem;
  }

  .hero {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 2.5rem;
    align-items: center;
    margin-bottom: 2.2rem;
  }

  .hero h1 {
    margin: 0.8rem 0 0.8rem;
    font-size: 2.6rem;
    line-height: 1.1;
  }

  .hero h1 span {
    display: block;
  }

  .intro {
    margin: 0;
    font-size: 1.08rem;
    color: var(--muted);
    max-width: 34rem;
  }

  .lanes {
    display: grid;
    gap: 0.4rem;
    padding: 1rem;
    border: 1px solid var(--border);
    border-radius: 18px;
    background: linear-gradient(180deg, var(--surface-2), var(--surface));
    box-shadow:
      var(--shadow),
      0 0 60px rgb(143 123 255 / 12%);
  }

  .lane {
    display: grid;
    grid-template-columns: 28px 70px 1fr;
    align-items: center;
    gap: 0.6rem;
    padding: 0.3rem 0.5rem;
    border-radius: 10px;
    background: color-mix(in srgb, var(--stem) 6%, transparent);
  }

  .lane-icon {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border-radius: 8px;
    color: var(--stem);
    background: color-mix(in srgb, var(--stem) 16%, transparent);
  }

  .lane-name {
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--muted);
  }

  .steps {
    display: flex;
    gap: 0.5rem;
    padding: 0;
    margin: 0 0 1.4rem;
    list-style: none;
    counter-reset: none;
  }

  .steps li {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.7rem 0.9rem;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    font-weight: 500;
  }

  .num {
    display: grid;
    place-items: center;
    flex: none;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--surface-3);
    font-size: 0.85rem;
    font-weight: 700;
  }

  .steps li.current {
    border-color: var(--accent);
    color: var(--fg);
    background: linear-gradient(180deg, var(--accent-soft), var(--surface));
  }

  .steps li.current .num {
    background: var(--gradient);
    color: #fff;
  }

  .steps li.done .num {
    background: var(--ok);
    color: #0a0a10;
  }

  .panel h4 {
    margin: 1.4rem 0 0.7rem;
    font-size: 0.95rem;
  }

  .lead {
    margin: 0 0 1rem;
    max-width: 46rem;
    line-height: 1.5;
  }

  .panel > .muted {
    font-size: 0.88rem;
    max-width: 46rem;
  }

  .next {
    margin: 0;
    padding-left: 1.3rem;
    display: grid;
    gap: 0.45rem;
    line-height: 1.45;
  }

  .panel h3 {
    margin: 0 0 0.6rem;
    font-size: 1.2rem;
  }

  .legal {
    display: flex;
    gap: 1rem;
    align-items: flex-start;
  }

  .legal p {
    margin: 0 0 1rem;
  }

  .legal-icon,
  .tile-icon {
    display: grid;
    place-items: center;
    flex: none;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    background: var(--accent-soft);
    color: var(--accent);
  }

  .accept {
    flex-wrap: nowrap;
    font-weight: 600;
  }

  .hw {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.8rem;
  }

  .tile {
    display: grid;
    gap: 0.3rem;
    align-content: start;
  }

  .tile-icon {
    margin-bottom: 0.4rem;
  }

  .tile.highlight {
    border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
  }

  .big {
    font-size: 1.4rem;
    font-family: var(--font-display);
  }

  .nav {
    margin-top: 1.8rem;
  }

  .spacer {
    flex: 1;
  }

  @media (max-width: 820px) {
    .hero {
      grid-template-columns: 1fr;
    }

    .steps {
      flex-direction: column;
    }
  }
</style>
