import { describe, expect, it } from "vitest";
import {
  applyEvent,
  displayName,
  itemLabel,
  itemProgress,
  revealTarget,
  stepName,
  type ItemView,
} from "./jobs";

const item: ItemView = {
  id: 7,
  input: "C:\\Music\\Song.flac",
  title: null,
  artist: null,
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

  it("names coarse steps", () => {
    expect(stepName("separate:sw")).toBe("separate");
    expect(stepName("export")).toBe("export");
    expect(stepName("analyse")).toBe("analyse");
    expect(stepName("mystery")).toBeNull();
  });

  it("reveals the first output file, or the folder before any exists", () => {
    expect(revealTarget("D:/Out", [item])).toBe("D:/Out");
    const done = { ...item, outputs: { Vocals: "D:/Out/Song - Vocals.wav" } };
    expect(revealTarget("D:/Out", [item, done])).toBe(
      "D:/Out/Song - Vocals.wav",
    );
  });

  it("shows file names and keeps links", () => {
    expect(displayName("C:\\Music\\Song.flac")).toBe("Song.flac");
    expect(displayName("https://youtu.be/abc")).toBe("https://youtu.be/abc");
  });
});

describe("item names", () => {
  it("shows the file name until title and artist arrive", () => {
    expect(itemLabel(item)).toEqual({ title: "Song.flac", artist: "" });
    const named = applyEvent([item], {
      seq: 1,
      type: "item.meta",
      item: 7,
      title: "Night Drive",
      artist: "The Testers",
    })[0];
    expect(itemLabel(named)).toEqual({
      title: "Night Drive",
      artist: "The Testers",
    });
  });

  it("ignores empty metadata", () => {
    const named = applyEvent([item], {
      seq: 1,
      type: "item.meta",
      item: 7,
      title: "",
      artist: null,
    })[0];
    expect(itemLabel(named).title).toBe("Song.flac");
  });
});
