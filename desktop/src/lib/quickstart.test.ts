import { describe, expect, it } from "vitest";
import type { Schemas } from "./api/client";
import {
  exampleJob,
  formatDuration,
  installProgress,
  pendingMb,
  quickStep,
  recommendedModels,
} from "./quickstart";

const model = (
  id: string,
  size_mb: number,
  installed = false,
): Schemas["ModelOut"] => ({
  id,
  name: id,
  stems: ["vocals"],
  size_mb,
  vram_mb_fp16: 1000,
  licence_class: "permissive",
  licence: "MIT",
  licence_url: "https://example.org/licence",
  verified_on: "2026-11-03",
  source: "https://example.org",
  notice: "",
  recommended_for: [],
  installed,
});

const catalogue = [model("sw", 600), model("res", 200), model("demucs", 50)];

describe("first-run quick start", () => {
  it("picks the models the recommended preset needs", () => {
    expect(recommendedModels(["sw"], catalogue).map((m) => m.id)).toEqual([
      "sw",
    ]);
    expect(
      recommendedModels(["res", "sw"], catalogue).map((m) => m.id),
    ).toEqual(["sw", "res"]);
    expect(recommendedModels(undefined, catalogue)).toEqual([]);
  });

  it("waits for the engine, then the runtime, before installing", () => {
    const models = [model("sw", 600)];
    const base = { ready: true, runtimeReady: true, models, installing: false };
    expect(quickStep({ ...base, ready: false })).toBe("engine");
    expect(quickStep({ ...base, models: [] })).toBe("engine");
    expect(quickStep({ ...base, runtimeReady: false })).toBe("runtime");
    expect(quickStep(base)).toBe("install");
    expect(quickStep({ ...base, installing: true })).toBe("installing");
  });

  it("offers the example song once every recommended model is installed", () => {
    const models = [model("sw", 600, true), model("res", 200, true)];
    expect(
      quickStep({
        ready: true,
        runtimeReady: false,
        models,
        installing: false,
      }),
    ).toBe("example");
    expect(
      quickStep({
        ready: true,
        runtimeReady: true,
        models: [models[0], model("res", 200)],
        installing: false,
      }),
    ).toBe("install");
  });

  it("counts only the models still to download", () => {
    expect(pendingMb([model("sw", 600, true), model("res", 200)])).toBe(200);
  });

  it("weights install progress by model size", () => {
    const models = [model("sw", 600, true), model("res", 200)];
    expect(installProgress(models, {})).toBe(0.75);
    expect(installProgress(models, { res: 0.5 })).toBe(0.875);
    expect(installProgress(models, { res: 7 })).toBe(1);
    expect(installProgress([], {})).toBe(0);
  });

  it("separates the example song into every stem", () => {
    const job = exampleJob({
      path: "C:\\data\\library\\example\\clip.mp3",
      outputDir: "  ",
      suggestedDir: "C:\\data\\library\\example\\stems",
      format: "wav",
      allowCpu: true,
    });
    expect(job.inputs).toEqual(["C:\\data\\library\\example\\clip.mp3"]);
    expect(job.stems).toEqual([
      "vocals",
      "guitar",
      "drums",
      "bass",
      "piano",
      "other",
    ]);
    expect(job.preset).toBe("auto");
    expect(job.output_dir).toBe("C:\\data\\library\\example\\stems");
    expect(job.rights_confirmed).toBe(false);
    const chosen = exampleJob({
      path: "x",
      outputDir: "D:\\Stems",
      suggestedDir: "y",
      format: "flac",
      allowCpu: false,
    });
    expect(chosen.output_dir).toBe("D:\\Stems");
  });

  it("formats the clip length", () => {
    expect(formatDuration(28)).toBe("0:28");
    expect(formatDuration(61.6)).toBe("1:02");
  });
});
