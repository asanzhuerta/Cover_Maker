<script lang="ts">
  // M2 spike: play six synthetic stems from one AudioContext, sample-aligned,
  // and measure decoded-buffer memory for a typical song length.
  import { resolve } from "$app/paths";
  import { STEMS, stemLabel, type Stem } from "$lib/stems";

  const SECONDS = 240;
  const RATE = 44_100;
  const FREQ: Record<Stem, number> = {
    vocals: 440,
    guitar: 196,
    drums: 2,
    bass: 55,
    piano: 523.25,
    other: 330,
  };

  let ctx: AudioContext | null = null;
  let gains: Partial<Record<Stem, GainNode>> = {};
  let sources: AudioBufferSourceNode[] = [];
  let muted = $state<Record<string, boolean>>({});
  let soloed = $state<Stem | null>(null);
  let report = $state("");

  function synth(context: AudioContext, stem: Stem): AudioBuffer {
    const buffer = context.createBuffer(2, SECONDS * RATE, RATE);
    for (let ch = 0; ch < 2; ch++) {
      const data = buffer.getChannelData(ch);
      for (let i = 0; i < data.length; i++) {
        const t = i / RATE;
        data[i] =
          stem === "drums"
            ? (t * FREQ.drums) % 1 < 0.02
              ? Math.random() * 0.4
              : 0
            : 0.1 * Math.sin(2 * Math.PI * FREQ[stem] * t);
      }
    }
    return buffer;
  }

  function applyGains() {
    for (const stem of STEMS) {
      const audible = soloed ? soloed === stem : !muted[stem];
      gains[stem]?.gain.setTargetAtTime(
        audible ? 1 : 0,
        ctx!.currentTime,
        0.01,
      );
    }
  }

  async function play() {
    stop();
    ctx = new AudioContext({ sampleRate: RATE });
    const t0 = performance.now();
    const buffers = STEMS.map((stem) => synth(ctx!, stem));
    const buildMs = Math.round(performance.now() - t0);
    const startAt = ctx.currentTime + 0.2;
    gains = {};
    sources = STEMS.map((stem, i) => {
      const gain = ctx!.createGain();
      gain.connect(ctx!.destination);
      gains[stem] = gain;
      const source = ctx!.createBufferSource();
      source.buffer = buffers[i];
      source.connect(gain);
      source.start(startAt); // same start time for every stem = sample-aligned
      return source;
    });
    applyGains();
    const bufferMb = Math.round(
      (STEMS.length * 2 * SECONDS * RATE * 4) / 2 ** 20,
    );
    const heap = (
      performance as Performance & { memory?: { usedJSHeapSize: number } }
    ).memory;
    report =
      `6 × ${SECONDS}s stereo buffers: ~${bufferMb} MB float32, built in ${buildMs} ms` +
      (heap ? `, JS heap ${Math.round(heap.usedJSHeapSize / 2 ** 20)} MB` : "");
  }

  function stop() {
    sources.forEach((s) => s.stop());
    sources = [];
    ctx?.close();
    ctx = null;
  }

  function toggleMute(stem: Stem) {
    muted = { ...muted, [stem]: !muted[stem] };
    applyGains();
  }

  function toggleSolo(stem: Stem) {
    soloed = soloed === stem ? null : stem;
    applyGains();
  }
</script>

<main>
  <h1>Multi-stem playback spike</h1>
  <p>
    <button onclick={play}>Play</button> <button onclick={stop}>Stop</button>
  </p>
  <table>
    <tbody>
      {#each STEMS as stem (stem)}
        <tr>
          <td>{stemLabel(stem)}</td>
          <td
            ><button onclick={() => toggleMute(stem)}
              >{muted[stem] ? "Unmute" : "Mute"}</button
            ></td
          >
          <td
            ><button onclick={() => toggleSolo(stem)}
              >{soloed === stem ? "Unsolo" : "Solo"}</button
            ></td
          >
        </tr>
      {/each}
    </tbody>
  </table>
  <p data-testid="report">{report}</p>
  <p><a href={resolve("/")}>Back</a></p>
</main>

<style>
  main {
    max-width: 40rem;
    margin: 2rem auto;
    font-family: system-ui, "Segoe UI", sans-serif;
  }
</style>
