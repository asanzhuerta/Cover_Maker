import { describe, expect, it } from "vitest";
import {
  MIN_DB,
  dbToGain,
  decodedMb,
  effectiveGains,
  formatClock,
  formatDb,
  formatPan,
  formatTime,
  nodeGains,
  panGains,
  peaksPath,
  stemsNeeded,
  wavSeconds,
  wrapPosition,
  type StemControl,
} from "./mixer";

const flat = (db = 0): StemControl => ({
  db,
  muted: false,
  soloed: false,
  pan: 0,
});

describe("mixer gains", () => {
  it("converts dB and treats the bottom of the fader as silence", () => {
    expect(dbToGain(0)).toBe(1);
    expect(dbToGain(-6)).toBeCloseTo(0.501, 3);
    expect(dbToGain(MIN_DB)).toBe(0);
    expect(formatDb(MIN_DB)).toBe("−∞ dB");
    expect(formatDb(3)).toBe("+3.0 dB");
  });

  it("applies mute, then solo over everything else", () => {
    const controls = {
      vocals: { ...flat(), muted: true },
      guitar: flat(-6),
      drums: flat(),
    };
    expect(effectiveGains(controls)).toEqual({
      vocals: 0,
      guitar: dbToGain(-6),
      drums: 1,
    });
    controls.drums.soloed = true;
    expect(effectiveGains(controls)).toEqual({
      vocals: 0,
      guitar: 0,
      drums: 1,
    });
  });

  it("matches the engine formula for the player's gain nodes", () => {
    const gains = { vocals: 0, guitar: 0.5 };
    expect(nodeGains(gains, "keep", false)).toEqual({
      mix: 1,
      stems: { vocals: [-1, -1], guitar: [-0.5, -0.5] },
    });
    expect(nodeGains(gains, "drop", false)).toEqual({
      mix: 0,
      stems: { vocals: [0, 0], guitar: [0.5, 0.5] },
    });
    expect(nodeGains(gains, "drop", true)).toEqual({
      mix: 1,
      stems: { vocals: [0, 0], guitar: [0, 0] },
    });
  });

  it("pans with a balance law that keeps the centre at unity", () => {
    expect(panGains(0)).toEqual([1, 1]);
    expect(panGains(-1)).toEqual([1, 0]);
    expect(panGains(0.25)).toEqual([0.75, 1]);
    expect(panGains(3)).toEqual([0, 1]);
    // Guitar hard left with the residual kept: the right channel loses it.
    expect(nodeGains({ guitar: 1 }, "keep", false, { guitar: -1 })).toEqual({
      mix: 1,
      stems: { guitar: [0, -1] },
    });
    expect(formatPan(0)).toBe("C");
    expect(formatPan(-0.4)).toBe("L40");
    expect(formatPan(1)).toBe("R100");
  });

  it("only decodes stems that change the sound", () => {
    const gains = { vocals: 0, guitar: 1, drums: 1 };
    expect(stemsNeeded(gains, "keep")).toEqual(["vocals"]);
    expect(stemsNeeded(gains, "keep", { drums: 0.5 })).toEqual([
      "vocals",
      "drums",
    ]);
    expect(stemsNeeded(gains, "drop")).toEqual(["vocals", "guitar", "drums"]);
  });
});

describe("mixer helpers", () => {
  it("estimates song length and decoded memory", () => {
    expect(wavSeconds(44 + 44_100 * 8 * 240)).toBeCloseTo(240);
    expect(decodedMb(240, 7, 44_100)).toBeCloseTo(565.2, 0);
  });

  it("formats times and wraps loop positions", () => {
    expect(formatTime(61.7)).toBe("1:01");
    expect(formatClock(187.46)).toBe("03:07.4");
    expect(formatClock(0)).toBe("00:00.0");
    expect(wrapPosition(5, { start: 2, end: 4 })).toBe(3);
    expect(wrapPosition(3, { start: 2, end: 4 })).toBe(3);
    expect(wrapPosition(5, null)).toBe(5);
  });

  it("draws a closed waveform path from peaks", () => {
    const path = peaksPath(
      [
        [-0.5, 0.5],
        [-1, 1],
      ],
      100,
      20,
    );
    expect(path.startsWith("M0.0 5.0L50.0 0.0")).toBe(true);
    expect(path.endsWith("Z")).toBe(true);
    expect(peaksPath([], 100, 20)).toBe("");
  });
});
