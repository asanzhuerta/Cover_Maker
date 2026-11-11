import { describe, expect, it } from "vitest";
import { midiProgress, overallFraction, toggleStem } from "./midi";

describe("MIDI export", () => {
  it("reads progress events for its own item only", () => {
    const event = {
      seq: 3,
      type: "midi.progress",
      item: 7,
      stem: "bass",
      index: 1,
      total: 3,
      fraction: 0.5,
    };
    expect(midiProgress(event, 7)).toEqual({
      stem: "bass",
      index: 1,
      total: 3,
      fraction: 0.5,
    });
    expect(midiProgress(event, 8)).toBeNull();
    expect(midiProgress({ type: "item.progress", item: 7 }, 7)).toBeNull();
  });

  it("adds finished stems to the current one", () => {
    const at = (index: number, fraction: number) =>
      overallFraction({ stem: "x", index, total: 4, fraction });
    expect(at(0, 0)).toBe(0);
    expect(at(1, 0.5)).toBeCloseTo(0.375);
    expect(at(3, 1)).toBe(1);
    expect(at(3, 7)).toBe(1);
    expect(
      overallFraction({ stem: "x", index: 0, total: 0, fraction: 1 }),
    ).toBe(0);
  });

  it("toggles stems in lane order", () => {
    const all = ["vocals", "drums", "bass"] as const;
    expect(toggleStem([], "bass", all)).toEqual(["bass"]);
    expect(toggleStem(["bass"], "vocals", all)).toEqual(["vocals", "bass"]);
    expect(toggleStem(["vocals", "bass"], "vocals", all)).toEqual(["bass"]);
  });
});
