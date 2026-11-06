import { describe, expect, it } from "vitest";
import {
  MODEL_MARGIN,
  RUNTIME_MARGIN,
  freeBytesFromGb,
  modelBytes,
  modelFits,
  runtimeFits,
  type DiskPlan,
} from "./space";

const plan = (needed: number, free: number | null): DiskPlan => ({
  torch: "cu128",
  download_bytes: 3e9,
  disk_bytes: 5e9,
  needed_bytes: needed,
  free_bytes: free,
  folder: "C:\\Users\\x\\AppData\\Local\\Cover_Maker\\runtime",
});

describe("disk space checks", () => {
  it("needs the runtime plus a margin", () => {
    expect(runtimeFits(plan(5e9, 5e9 + RUNTIME_MARGIN))).toBe(true);
    expect(runtimeFits(plan(5e9, 5e9 + RUNTIME_MARGIN - 1))).toBe(false);
    expect(runtimeFits(plan(5e9, null))).toBe(true);
  });

  it("needs the model plus a margin", () => {
    const free = modelBytes(600) + MODEL_MARGIN;
    expect(modelFits(600, free)).toBe(true);
    expect(modelFits(600, free - 1)).toBe(false);
    expect(modelFits(600, null)).toBe(true);
  });

  it("converts the engine's free GB", () => {
    expect(freeBytesFromGb(1.5)).toBe(1.5 * 1024 ** 3);
  });
});
