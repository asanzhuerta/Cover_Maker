import { describe, expect, it } from "vitest";
import {
  baseName,
  formatBytes,
  newItemIds,
  selectedInputs,
  statusTone,
  syncSummary,
} from "./library";

describe("library helpers", () => {
  it("formats sizes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(150 * 1024 * 1024)).toBe("150 MB");
    expect(formatBytes(4.2 * 1024 ** 3)).toBe("4.2 GB");
  });

  it("maps match states to badge tones", () => {
    expect(statusTone("ready")).toBe("ok");
    expect(statusTone("needs_review")).toBe("warn");
    expect(statusTone("unavailable")).toBe("danger");
    expect(statusTone("other")).toBe("");
  });

  it("sends only matched, selected items to a job", () => {
    const items = [
      { id: 1, input: "C:\\a.wav", status: "ready" },
      { id: 2, input: "C:\\b.wav", status: "needs_review" },
      { id: 3, input: null, status: "unavailable" },
      { id: 4, input: "https://youtu.be/x", status: "ready" },
    ];
    expect(selectedInputs(items, new Set([1, 2, 3, 4]))).toEqual([
      "C:\\a.wav",
      "https://youtu.be/x",
    ]);
    expect(selectedInputs(items, new Set([2]))).toEqual([]);
  });

  it("selects only matched songs without stems", () => {
    const items = [
      { id: 1, status: "ready" },
      { id: 2, status: "ready" },
      { id: 3, status: "needs_review" },
      { id: 4, status: "ready" },
    ];
    expect(newItemIds(items, { 1: ["vocals"], 4: [] })).toEqual([2, 4]);
  });

  it("summarises a sync without zero counts", () => {
    expect(
      syncSummary({
        added: 2,
        removed: 0,
        unchanged: 5,
        needs_review: 1,
        unavailable: 0,
      }),
    ).toEqual([
      ["added", 2],
      ["unchanged", 5],
      ["needs_review", 1],
    ]);
  });

  it("names files and links", () => {
    expect(baseName("C:\\Music\\Song.flac")).toBe("Song.flac");
    expect(baseName("https://www.youtube.com/watch?v=abc")).toBe("watch?v=abc");
  });
});
