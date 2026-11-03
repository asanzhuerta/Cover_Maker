import { describe, expect, it } from "vitest";
import { waveBars } from "./wave";

describe("waveBars", () => {
  it("is deterministic per seed", () => {
    expect(waveBars("song.flac", 24)).toEqual(waveBars("song.flac", 24));
    expect(waveBars("song.flac", 24)).not.toEqual(waveBars("other.wav", 24));
  });

  it("keeps every bar visible and within range", () => {
    const bars = waveBars("x", 64);
    expect(bars).toHaveLength(64);
    for (const bar of bars) {
      expect(bar).toBeGreaterThanOrEqual(0.12);
      expect(bar).toBeLessThanOrEqual(1);
    }
  });
});
