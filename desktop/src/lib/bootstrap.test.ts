import { describe, expect, it } from "vitest";
import {
  needsSetup,
  phaseProgress,
  stepLabel,
  type BootstrapStatus,
  type PhaseStatus,
} from "./bootstrap.svelte";

const phase = (over: Partial<PhaseStatus>): PhaseStatus => ({
  state: "running",
  step: "python",
  index: 1,
  total: 5,
  fraction: null,
  detail: "",
  error: "",
  ...over,
});

describe("bootstrap", () => {
  it("counts finished steps and the current download", () => {
    expect(phaseProgress(phase({ index: 1 }))).toBe(0);
    expect(phaseProgress(phase({ index: 4, fraction: 0.5 }))).toBeCloseTo(0.7);
    expect(phaseProgress(phase({ state: "done" }))).toBe(1);
    expect(phaseProgress(phase({ total: 0 }))).toBeNull();
  });

  it("shows the setup screen only for an installed app without its core", () => {
    const status: BootstrapStatus = {
      mode: "runtime",
      core: phase({}),
      separation: phase({ state: "pending" }),
      torch: null,
    };
    expect(needsSetup(status)).toBe(true);
    expect(needsSetup({ ...status, core: phase({ state: "done" }) })).toBe(
      false,
    );
    expect(needsSetup({ ...status, mode: "development" })).toBe(false);
  });

  it("labels known steps", () => {
    expect(stepLabel("ffmpeg")).toBe("bootstrap.step.ffmpeg");
    expect(stepLabel("mystery")).toBeNull();
  });
});
