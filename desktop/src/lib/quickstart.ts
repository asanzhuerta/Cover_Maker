/**
 * First-run quick win: install the models recommended for this PC with one
 * click (after the user accepts their licence notices), then separate the
 * bundled Creative Commons example song into every stem.
 */
import type { Schemas } from "./api/client";
import { STEMS } from "./stems";

type Model = Schemas["ModelOut"];
type JobRequest = Schemas["JobRequest"];

/**
 * Where the quick start stands:
 * - `engine`: waiting for the engine (or its model list);
 * - `runtime`: the separation runtime is still downloading;
 * - `install`: ready to install the recommended models;
 * - `installing`: downloading them;
 * - `example`: everything is installed, the example song can run.
 */
export type QuickStep =
  "engine" | "runtime" | "install" | "installing" | "example";

/** The catalogue models the recommended preset needs, in catalogue order. */
export function recommendedModels(
  recommended: readonly string[] | undefined,
  models: readonly Model[],
): Model[] {
  if (!recommended?.length) return [];
  return models.filter((model) => recommended.includes(model.id));
}

export function quickStep(options: {
  ready: boolean;
  runtimeReady: boolean;
  models: readonly Model[];
  installing: boolean;
}): QuickStep {
  if (!options.ready || options.models.length === 0) return "engine";
  if (options.models.every((model) => model.installed)) return "example";
  if (options.installing) return "installing";
  if (!options.runtimeReady) return "runtime";
  return "install";
}

/** Models still to download, so a half-finished install resumes. */
export function pending(models: readonly Model[]): Model[] {
  return models.filter((model) => !model.installed);
}

/** Download size of the models still to install, in MB. */
export function pendingMb(models: readonly Model[]): number {
  return pending(models).reduce((sum, model) => sum + model.size_mb, 0);
}

/**
 * Overall progress in [0, 1] of a multi-model install, weighted by size.
 * Installed models count as finished; models without an event yet as 0.
 */
export function installProgress(
  models: readonly Model[],
  progress: Readonly<Record<string, number>>,
): number {
  const total = models.reduce((sum, model) => sum + model.size_mb, 0);
  if (total === 0) return 0;
  const done = models.reduce(
    (sum, model) =>
      sum +
      model.size_mb *
        (model.installed
          ? 1
          : Math.min(1, Math.max(0, progress[model.id] ?? 0))),
    0,
  );
  return done / total;
}

/** "0:28" for 28 seconds. */
export function formatDuration(seconds: number): string {
  const whole = Math.max(0, Math.round(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/**
 * The job for the example song: every stem with the preset recommended for
 * this PC, into the user's output folder or the engine's suggestion.
 */
export function exampleJob(options: {
  path: string;
  outputDir: string;
  suggestedDir: string;
  format: JobRequest["output_format"];
  allowCpu: boolean;
}): JobRequest {
  return {
    inputs: [options.path],
    stems: [...STEMS],
    mode: "extract",
    residual: "keep",
    preset: "auto",
    output_dir: options.outputDir.trim() || options.suggestedDir,
    output_format: options.format,
    allow_cpu_fallback: options.allowCpu,
    rights_confirmed: false,
  };
}
