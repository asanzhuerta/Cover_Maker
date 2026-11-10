<script lang="ts">
  // Temporary M13 page: compare the three logo directions (removed after the choice).
  import Logo, { type LogoVariant } from "$lib/components/Logo.svelte";

  const OPTIONS: { variant: LogoVariant; name: string; idea: string }[] = [
    {
      variant: "reel",
      name: "A · Reel",
      idea: "A tape reel opens into a C; the tape leaving it is the underscore.",
    },
    {
      variant: "fader",
      name: "B · Fader",
      idea: "A console fader; the line on the cap is the underscore.",
    },
    {
      variant: "cursor",
      name: "C · Cursor",
      idea: "C_ as a typed prompt; the underscore blinks like a cursor or playhead.",
    },
  ];
</script>

<header class="page-head">
  <div>
    <h1>Logo options</h1>
    <p>Three directions for Tape &amp; Console. Pick one.</p>
  </div>
</header>

{#each OPTIONS as option (option.variant)}
  <section class="card option" data-testid="logo-{option.variant}">
    <div class="intro">
      <h3>{option.name}</h3>
      <p class="muted">{option.idea}</p>
    </div>
    <div class="row sizes">
      <div class="tile dark"><Logo variant={option.variant} size={128} /></div>
      <div class="tile light"><Logo variant={option.variant} size={128} /></div>
      <div class="icons">
        <div class="app"><Logo variant={option.variant} size={64} /></div>
        <div class="app small"><Logo variant={option.variant} size={30} /></div>
        <div class="app tiny"><Logo variant={option.variant} size={14} /></div>
        <span class="label">App icon</span>
      </div>
      <div class="lockups">
        <div class="lockup dark">
          <Logo variant={option.variant} size={44} />
          <div>
            <strong>Cover<span class="u">_</span>Maker</strong>
            <span class="desc">the cover musician's studio</span>
          </div>
        </div>
        <div class="lockup light">
          <Logo variant={option.variant} size={44} />
          <div>
            <strong>Cover<span class="u">_</span>Maker</strong>
            <span class="desc">the cover musician's studio</span>
          </div>
        </div>
      </div>
    </div>
  </section>
{/each}

<style>
  .option {
    display: grid;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .intro h3 {
    margin: 0 0 0.2rem;
  }

  .intro p {
    margin: 0;
  }

  .sizes {
    gap: 1rem;
    align-items: stretch;
  }

  .tile {
    display: grid;
    place-items: center;
    width: 168px;
    height: 168px;
    border-radius: var(--radius);
  }

  .dark {
    background: #0c0b0a;
    color: #f1e9dc;
  }

  .light {
    background: #f3ede2;
    color: #1d1a16;
  }

  .icons {
    display: grid;
    grid-template-columns: auto auto auto;
    align-items: center;
    align-content: center;
    gap: 0.8rem;
  }

  .icons .label {
    grid-column: 1 / -1;
  }

  /* Round chassis, like a knob or a reel: not a rounded tile. */
  .app {
    display: grid;
    place-items: center;
    width: 96px;
    height: 96px;
    border-radius: 50%;
    background: #15130f;
    color: #f1e9dc;
    box-shadow:
      inset 0 0 0 2px #29251f,
      0 4px 12px rgb(0 0 0 / 40%);
  }

  .app.small {
    width: 40px;
    height: 40px;
  }

  .app.tiny {
    width: 18px;
    height: 18px;
    box-shadow: none;
  }

  .lockups {
    display: grid;
    gap: 0.6rem;
    flex: 1;
    min-width: 260px;
  }

  .lockup {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    padding: 0.9rem 1rem;
    border-radius: var(--radius);
  }

  .lockup strong {
    display: block;
    font-family: var(--font-display);
    font-size: 1.5rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }

  .u {
    color: #ff6a3d;
  }

  .desc {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    opacity: 0.75;
  }
</style>
