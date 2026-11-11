<script lang="ts">
  let {
    value = $bindable(0),
    min = -1,
    max = 1,
    step = 0.05,
    resetTo = 0,
    label,
    valueText,
    size = 34,
    snap,
    testid,
  }: {
    value?: number;
    min?: number;
    max?: number;
    /** Change per arrow key press. */
    step?: number;
    /** Value restored by double-click, Delete or Backspace. */
    resetTo?: number;
    label: string;
    valueText: string;
    size?: number;
    /** Values snap to multiples of this (default: a fifth of `step`). */
    snap?: number;
    testid?: string;
  } = $props();

  const SWEEP = 135;
  const DRAG_PX = 160;

  const clamp = (v: number) => Math.min(max, Math.max(min, v));
  const angleOf = (v: number) => -SWEEP + ((v - min) / (max - min)) * SWEEP * 2;
  const angle = $derived(angleOf(value));
  const origin = $derived(angleOf(clamp(resetTo)));

  function point(degrees: number, radius: number): string {
    const rad = (degrees * Math.PI) / 180;
    return `${(20 + radius * Math.sin(rad)).toFixed(2)} ${(20 - radius * Math.cos(rad)).toFixed(2)}`;
  }

  function arc(from: number, to: number): string {
    const [a, b] = from <= to ? [from, to] : [to, from];
    if (b - a < 0.5) return "";
    return `M${point(a, 17)}A17 17 0 ${b - a > 180 ? 1 : 0} 1 ${point(b, 17)}`;
  }

  function set(next: number) {
    const grain = snap ?? step / 5;
    value = Math.round(clamp(next) / grain) * grain;
  }

  let dragFrom: { y: number; value: number } | null = null;

  function pointerDown(event: PointerEvent) {
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    dragFrom = { y: event.clientY, value };
  }

  function pointerMove(event: PointerEvent) {
    if (!dragFrom) return;
    const fine = event.shiftKey ? 0.2 : 1;
    const delta = ((dragFrom.y - event.clientY) / DRAG_PX) * (max - min) * fine;
    set(dragFrom.value + delta);
  }

  function keydown(event: KeyboardEvent) {
    const moves: Record<string, number> = {
      ArrowUp: step,
      ArrowRight: step,
      ArrowDown: -step,
      ArrowLeft: -step,
      PageUp: step * 5,
      PageDown: -step * 5,
    };
    if (event.key in moves) set(value + moves[event.key]);
    else if (event.key === "Home") set(min);
    else if (event.key === "End") set(max);
    else if (event.key === "Delete" || event.key === "Backspace") set(resetTo);
    else return;
    event.preventDefault();
    event.stopPropagation();
  }
</script>

<div
  class="knob"
  role="slider"
  tabindex="0"
  aria-label={label}
  aria-valuemin={min}
  aria-valuemax={max}
  aria-valuenow={Math.round(value * 100) / 100}
  aria-valuetext={valueText}
  title="{label}: {valueText}"
  style="--size: {size}px"
  data-testid={testid}
  onpointerdown={pointerDown}
  onpointermove={pointerMove}
  onpointerup={() => (dragFrom = null)}
  onpointercancel={() => (dragFrom = null)}
  ondblclick={() => set(resetTo)}
  onkeydown={keydown}
>
  <svg viewBox="0 0 40 40" aria-hidden="true">
    <path class="track" d={arc(-SWEEP, SWEEP)} />
    <path class="value" d={arc(origin, angle)} />
    <circle class="cap" cx="20" cy="20" r="12" />
    <path class="pointer" d="M{point(angle, 5)}L{point(angle, 11)}" />
  </svg>
</div>

<style>
  .knob {
    width: var(--size);
    height: var(--size);
    flex: none;
    border-radius: 50%;
    cursor: ns-resize;
    touch-action: none;
  }

  svg {
    display: block;
    width: 100%;
    height: 100%;
    overflow: visible;
  }

  path {
    fill: none;
    stroke-linecap: round;
  }

  .track {
    stroke: var(--surface-3);
    stroke-width: 3;
  }

  .value {
    stroke: var(--knob, var(--accent));
    stroke-width: 3;
  }

  .cap {
    fill: var(--surface-2);
    stroke: var(--border-strong);
    stroke-width: 1;
    filter: drop-shadow(0 1px 1px rgb(0 0 0 / 45%));
  }

  .pointer {
    stroke: var(--fg);
    stroke-width: 2.4;
  }
</style>
