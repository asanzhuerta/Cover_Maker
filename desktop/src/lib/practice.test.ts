import { describe, expect, it } from "vitest";
import {
  ACCENT_LEVEL,
  CLICK_LEVEL,
  barAt,
  clampTempo,
  countInSeconds,
  foldCents,
  formatCents,
  formatShift,
  formatTempo,
  freshTrainer,
  loopWrapped,
  nextMarkerName,
  pitchCorrection,
  renderClick,
  sectionRegion,
  shiftedKey,
  snapRegion,
  snapToBar,
  trainerDone,
  trainerTempo,
} from "./practice";

const bars = [0.5, 2.5, 4.5, 6.5];

describe("pitch and tempo", () => {
  it("cancels the resample pitch and adds the user's shift", () => {
    expect(pitchCorrection(1, 0, 0)).toBe(0);
    expect(pitchCorrection(2, 0, 0)).toBeCloseTo(-12);
    expect(pitchCorrection(0.5, -1, 30)).toBeCloseTo(12 - 1 + 0.3);
    for (const tempo of [0.5, 0.8, 1.25, 1.5])
      expect(
        12 * Math.log2(tempo) + pitchCorrection(tempo, 3, -20),
      ).toBeCloseTo(2.8);
  });

  it("keeps the tempo between 50 and 150 %", () => {
    expect(clampTempo(0.2)).toBe(0.5);
    expect(clampTempo(2)).toBe(1.5);
    expect(formatTempo(0.8)).toBe("80 %");
  });

  it("names the shifted key", () => {
    expect(shiftedKey("E", "major", -1)).toBe("Eb");
    expect(shiftedKey("A", "minor", 3)).toBe("Cm");
    expect(shiftedKey("C", "major", -13)).toBe("B");
  });

  it("folds and formats cents", () => {
    expect(foldCents(60)).toBe(-40);
    expect(foldCents(-50)).toBe(-50);
    expect(formatCents(0)).toBe("±0");
    expect(formatCents(-12.4)).toBe("−12");
    expect(formatShift(-1, 0)).toBe("−1 st");
    expect(formatShift(0, 0)).toBe("0 st");
  });
});

describe("bars and loops", () => {
  it("snaps to the nearest bar line", () => {
    expect(snapToBar(2.0, bars)).toBe(2.5);
    expect(snapToBar(1.4, bars)).toBe(0.5);
    expect(snapToBar(3, [])).toBe(3);
  });

  it("keeps a snapped loop at least one bar long", () => {
    expect(snapRegion({ start: 2.4, end: 4.7 }, bars, 8)).toEqual({
      start: 2.5,
      end: 4.5,
    });
    expect(snapRegion({ start: 2.4, end: 2.9 }, bars, 8)).toEqual({
      start: 2.5,
      end: 4.5,
    });
    expect(snapRegion({ start: 6.4, end: 7.9 }, bars, 8)).toEqual({
      start: 6.5,
      end: 8,
    });
    expect(snapRegion({ start: 1, end: 2 }, [], 8)).toEqual({
      start: 1,
      end: 2,
    });
  });

  it("counts bars from the first downbeat", () => {
    expect(barAt(0.2, bars)).toBe(0);
    expect(barAt(0.5, bars)).toBe(1);
    expect(barAt(5, bars)).toBe(3);
  });

  it("detects a loop pass", () => {
    const loop = { start: 2, end: 6 };
    expect(loopWrapped(5.9, 2.1, loop)).toBe(true);
    expect(loopWrapped(3, 3.1, loop)).toBe(false);
    expect(loopWrapped(4, 3.8, loop)).toBe(false); // a small seek back
    expect(loopWrapped(5.9, 2.1, null)).toBe(false);
  });
});

describe("markers", () => {
  const markers = [
    { name: "Chorus", time: 30 },
    { name: "Intro", time: 0 },
  ];

  it("loops a section up to the next marker or the end", () => {
    expect(sectionRegion(markers, 0, 90)).toEqual({ start: 0, end: 30 });
    expect(sectionRegion(markers, 1, 90)).toEqual({ start: 30, end: 90 });
    expect(sectionRegion(markers, 2, 90)).toBeNull();
  });

  it("suggests a free name", () => {
    expect(nextMarkerName([], "Section")).toBe("Section 1");
    expect(nextMarkerName([{ name: "Section 2", time: 0 }], "Section")).toBe(
      "Section 3",
    );
  });
});

describe("count-in and trainer", () => {
  it("lasts one bar at the played tempo", () => {
    expect(countInSeconds(120, 1)).toBe(2);
    expect(countInSeconds(120, 0.5)).toBe(4);
    expect(countInSeconds(0, 1)).toBe(0);
  });

  it("raises the tempo every N passes up to the target", () => {
    const trainer = {
      ...freshTrainer(),
      start: 0.7,
      step: 0.1,
      every: 2,
      target: 1,
    };
    expect([0, 1, 2, 3, 4, 6, 20].map((p) => trainerTempo(trainer, p))).toEqual(
      [0.7, 0.7, 0.8, 0.8, 0.9, 1, 1],
    );
    expect(trainerDone(trainer, 5)).toBe(false);
    expect(trainerDone(trainer, 6)).toBe(true);
  });

  it("can also slow down towards a lower target", () => {
    const trainer = {
      ...freshTrainer(),
      start: 1,
      step: 0.1,
      every: 1,
      target: 0.8,
    };
    expect([0, 1, 2, 5].map((p) => trainerTempo(trainer, p))).toEqual([
      1, 0.9, 0.8, 0.8,
    ]);
  });
});

describe("click", () => {
  it("places a blip on every beat, louder on downbeats", () => {
    const rate = 8000;
    const click = renderClick(rate, rate * 3, [0.5, 1, 1.5, 2.5], [0.5]);
    const peak = (at: number) =>
      Math.max(
        ...Array.from(
          click.slice(at * rate, at * rate + 0.03 * rate),
          Math.abs,
        ),
      );

    expect(peak(0.5)).toBeGreaterThan(CLICK_LEVEL);
    expect(peak(0.5)).toBeLessThanOrEqual(ACCENT_LEVEL);
    expect(peak(1)).toBeLessThanOrEqual(CLICK_LEVEL);
    expect(peak(1)).toBeGreaterThan(0.1);
    expect(click.slice(0, 0.5 * rate).every((v) => v === 0)).toBe(true);
  });

  it("skips beats outside the buffer", () => {
    const click = renderClick(8000, 800, [-1, 5], []);
    expect(click.every((v) => v === 0)).toBe(true);
  });
});
