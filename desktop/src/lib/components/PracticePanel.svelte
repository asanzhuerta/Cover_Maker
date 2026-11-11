<script lang="ts">
  // Practice tools (M14): pitch, fine tune and tempo knobs, click and
  // count-in, bar-snapped loops, the speed trainer and section markers.
  import Icon from "$lib/components/Icon.svelte";
  import Knob from "$lib/components/Knob.svelte";
  import { t } from "$lib/i18n.svelte";
  import { formatClock } from "$lib/mixer";
  import {
    formatCents,
    formatShift,
    formatTempo,
    trainerDone,
  } from "$lib/practice";
  import {
    addMarker,
    loopSection,
    removeMarker,
    renameMarker,
    resetPractice,
    seek,
    setTrainer,
    transport,
    tuneToA440,
  } from "$lib/transport.svelte";

  let markerName = $state("");

  const practice = $derived(transport.practice);
  const trainer = $derived(transport.trainer);
  const analysis = $derived(transport.analysis);
  const hasGrid = $derived((analysis?.beats.length ?? 0) > 0);
  const percent = (value: number) => Math.round(value * 100);

  function add() {
    addMarker(t("practice.markerBase"), markerName);
    markerName = "";
  }
</script>

<section
  class="card practice"
  aria-labelledby="practice-title"
  data-testid="practice"
>
  <header class="row head">
    <h2 id="practice-title">{t("practice.title")}</h2>
    {#if !analysis}
      <span class="muted small-text" role="status"
        >{t("practice.analysing")}</span
      >
    {:else if !hasGrid}
      <span class="muted small-text">{t("practice.noGrid")}</span>
    {/if}
    <button class="small ghost" onclick={resetPractice}
      ><Icon name="reset" size={14} />{t("practice.reset")}</button
    >
  </header>

  <div class="grid">
    <div class="group knobs" role="group" aria-label={t("practice.pitch")}>
      <div class="knob-cell">
        <Knob
          bind:value={practice.semitones}
          min={-12}
          max={12}
          step={1}
          snap={1}
          size={46}
          label={t("practice.pitch")}
          valueText={formatShift(practice.semitones, 0)}
          testid="pitch"
        />
        <span class="caps">{t("practice.pitch")}</span>
        <span class="readout mono">{formatShift(practice.semitones, 0)}</span>
      </div>
      <div class="knob-cell">
        <Knob
          bind:value={practice.cents}
          min={-50}
          max={50}
          step={1}
          snap={1}
          size={46}
          label={t("practice.fine")}
          valueText="{formatCents(practice.cents)} ¢"
          testid="cents"
        />
        <span class="caps">{t("practice.fine")}</span>
        <span class="readout mono">{formatCents(practice.cents)} ¢</span>
      </div>
      <div class="knob-cell">
        <Knob
          bind:value={practice.tempo}
          min={0.5}
          max={1.5}
          step={0.01}
          snap={0.01}
          resetTo={1}
          size={46}
          label={t("practice.tempo")}
          valueText={formatTempo(practice.tempo)}
          testid="tempo"
        />
        <span class="caps">{t("practice.tempo")}</span>
        <span class="readout mono">{formatTempo(practice.tempo)}</span>
      </div>
      <button
        class="small"
        disabled={!analysis || Math.round(analysis.tuning_cents) === 0}
        title={analysis
          ? t("practice.a440Hint").replace(
              "{cents}",
              formatCents(analysis.tuning_cents),
            )
          : ""}
        onclick={tuneToA440}
        data-testid="a440">{t("practice.a440")}</button
      >
    </div>

    <div class="group toggles">
      <label class="check">
        <input
          type="checkbox"
          bind:checked={practice.click}
          disabled={!hasGrid}
          data-testid="click"
        />{t("practice.click")}
      </label>
      <div class="knob-cell inline">
        <Knob
          bind:value={practice.clickDb}
          min={-30}
          max={6}
          step={1}
          snap={0.5}
          resetTo={-6}
          size={28}
          label={t("practice.clickLevel")}
          valueText="{practice.clickDb.toFixed(1)} dB"
          testid="click-level"
        />
        <span class="readout mono">{practice.clickDb.toFixed(0)} dB</span>
      </div>
      <label class="check" title={t("practice.countInHint")}>
        <input
          type="checkbox"
          bind:checked={practice.countIn}
          disabled={!hasGrid}
          data-testid="count-in"
        />{t("practice.countIn")}
      </label>
      <label class="check">
        <input
          type="checkbox"
          bind:checked={practice.snap}
          disabled={!hasGrid}
          data-testid="snap"
        />{t("practice.snap")}
      </label>
      {#if transport.counting}<span class="badge" role="status"
          >{t("practice.countingIn")}</span
        >{/if}
    </div>

    <fieldset class="group trainer" data-testid="trainer">
      <legend title={t("practice.trainerHint")}>{t("practice.trainer")}</legend>
      <label
        >{t("practice.from")}
        <input
          type="number"
          min="50"
          max="150"
          step="5"
          value={percent(trainer.start)}
          onchange={(e) =>
            (trainer.start = Number(e.currentTarget.value) / 100)}
          disabled={trainer.on}
        /> %</label
      >
      <label
        >{t("practice.step")}
        <input
          type="number"
          min="1"
          max="25"
          step="1"
          value={percent(trainer.step)}
          onchange={(e) => (trainer.step = Number(e.currentTarget.value) / 100)}
          disabled={trainer.on}
        /> %</label
      >
      <label
        >{t("practice.every")}
        <input
          type="number"
          min="1"
          max="20"
          step="1"
          bind:value={trainer.every}
          disabled={trainer.on}
        /></label
      >
      <label
        >{t("practice.target")}
        <input
          type="number"
          min="50"
          max="150"
          step="5"
          value={percent(trainer.target)}
          onchange={(e) =>
            (trainer.target = Number(e.currentTarget.value) / 100)}
          disabled={trainer.on}
        /> %</label
      >
      <button
        class="small led-button"
        aria-pressed={trainer.on}
        onclick={() => setTrainer(!trainer.on)}
        data-testid="trainer-toggle"
        >{trainer.on
          ? t("practice.trainerStop")
          : t("practice.trainerStart")}</button
      >
      {#if trainer.on}
        <span
          class="mono status"
          class:done={trainerDone(trainer, transport.passes)}
          role="status"
          >{t("practice.status")
            .replace("{tempo}", formatTempo(practice.tempo))
            .replace("{passes}", String(transport.passes))}</span
        >
      {/if}
    </fieldset>
  </div>

  <div class="markers">
    <h3>{t("practice.markers")}</h3>
    <form
      class="row"
      onsubmit={(event) => {
        event.preventDefault();
        add();
      }}
    >
      <input
        type="text"
        maxlength="40"
        bind:value={markerName}
        placeholder={t("practice.markerPlaceholder")}
        aria-label={t("practice.markerName")}
        data-testid="marker-name"
      />
      <button class="small" type="submit" data-testid="add-marker"
        >{t("practice.addMarker").replace(
          "{time}",
          formatClock(transport.position),
        )}</button
      >
    </form>
    {#if transport.markers.length === 0}
      <p class="muted small-text">{t("practice.noMarkers")}</p>
    {:else}
      <ol class="marker-list" data-testid="markers">
        {#each transport.markers as marker, index (index)}
          <li>
            <button
              class="small ghost mono"
              title={t("practice.goTo")}
              onclick={() => seek(marker.time)}
              >{formatClock(marker.time)}</button
            >
            <input
              type="text"
              maxlength="40"
              value={marker.name}
              aria-label={t("practice.markerName")}
              onchange={(e) => renameMarker(index, e.currentTarget.value)}
            />
            <button
              class="small"
              onclick={() => loopSection(index)}
              title={t("practice.loopSection")}
              aria-label="{t('practice.loopSection')}: {marker.name}"
              ><Icon name="loop" size={14} /></button
            >
            <button
              class="small ghost"
              onclick={() => removeMarker(index)}
              aria-label="{t('practice.removeMarker')}: {marker.name}">×</button
            >
          </li>
        {/each}
      </ol>
    {/if}
  </div>
</section>

<style>
  .practice {
    display: grid;
    gap: 1rem;
  }

  .head {
    align-items: center;
    gap: 0.8rem;
    flex-wrap: wrap;
  }

  .head h2 {
    margin: 0;
    font-size: 1rem;
  }

  .head button {
    margin-left: auto;
  }

  .small-text {
    font-size: 0.82rem;
  }

  .grid {
    display: grid;
    grid-template-columns: auto auto minmax(0, 1fr);
    gap: 1.4rem;
    align-items: start;
  }

  .group {
    display: flex;
    gap: 0.9rem;
    align-items: center;
    flex-wrap: wrap;
  }

  .knob-cell {
    display: grid;
    justify-items: center;
    gap: 0.15rem;
  }

  .knob-cell.inline {
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .caps {
    font-size: 0.62rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    opacity: 0.75;
  }

  .readout {
    font-size: 0.78rem;
  }

  .toggles {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.45rem;
  }

  .check {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.88rem;
  }

  .trainer {
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    padding: 0.5rem 0.8rem 0.7rem;
    margin: 0;
    gap: 0.6rem;
  }

  .trainer legend {
    font-size: 0.82rem;
    font-weight: 600;
    padding: 0 0.3rem;
  }

  .trainer label {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.82rem;
  }

  .trainer input {
    width: 4.2rem;
  }

  .status.done {
    color: var(--led-green);
  }

  .markers h3 {
    margin: 0 0 0.4rem;
    font-size: 0.9rem;
  }

  .markers form input {
    flex: 1;
    max-width: 18rem;
  }

  .marker-list {
    list-style: none;
    margin: 0.5rem 0 0;
    padding: 0;
    display: grid;
    gap: 0.3rem;
  }

  .marker-list li {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .marker-list input {
    flex: 1;
    max-width: 18rem;
  }

  @media (max-width: 1100px) {
    .grid {
      grid-template-columns: 1fr;
    }
  }
</style>
