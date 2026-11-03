import { describe, expect, it } from "vitest";
import { applyEvent, displayName, itemProgress, type ItemView } from "./jobs";
import { detectLocale, translate } from "./i18n.svelte";

const item: ItemView = {
  id: 7,
  input: "C:\\Music\\Song.flac",
  status: "pending",
  step: null,
  fraction: null,
  error: null,
  outputs: {},
};

describe("job progress", () => {
  it("advances with steps and finishes at 100 %", () => {
    let items = applyEvent([item], {
      seq: 1,
      type: "item.step",
      item: 7,
      step: "separate:sw",
    });
    expect(itemProgress(items[0])).toBeCloseTo(0.85);
    items = applyEvent(items, {
      seq: 2,
      type: "item.done",
      item: 7,
      outputs: { Vocals: "x.wav" },
    });
    expect(items[0].status).toBe("done");
    expect(itemProgress(items[0])).toBe(1);
    expect(items[0].outputs).toEqual({ Vocals: "x.wav" });
  });

  it("scales the download step by its fraction", () => {
    let items = applyEvent([item], {
      seq: 1,
      type: "item.step",
      item: 7,
      step: "download",
    });
    items = applyEvent(items, {
      seq: 2,
      type: "item.progress",
      item: 7,
      fraction: 0.5,
    });
    expect(itemProgress(items[0])).toBeCloseTo(0.075);
  });

  it("ignores events for other items", () => {
    const items = applyEvent([item], {
      seq: 1,
      type: "item.failed",
      item: 8,
      error: "x",
    });
    expect(items[0]).toBe(item);
  });

  it("shows file names and keeps links", () => {
    expect(displayName("C:\\Music\\Song.flac")).toBe("Song.flac");
    expect(displayName("https://youtu.be/abc")).toBe("https://youtu.be/abc");
  });
});

describe("i18n", () => {
  it("picks Spanish for es-* browsers and English otherwise", () => {
    expect(detectLocale("es-ES")).toBe("es");
    expect(detectLocale("de-DE")).toBe("en");
  });

  it("has every key translated", () => {
    expect(translate("es", "stem.guitar")).toBe("Guitarra");
    expect(translate("en", "stem.guitar")).toBe("Guitar");
  });
});
