/**
 * First-run bootstrap of the engine runtime, driven by the Tauri shell
 * (ADR-006). Phase A (core) must finish before the engine starts; phase B
 * (separation runtime with PyTorch) runs in the background afterwards.
 */
import type { MessageKey } from "./i18n.svelte";

export interface PhaseStatus {
  state: "pending" | "running" | "done" | "failed";
  step: string;
  index: number;
  total: number;
  fraction: number | null;
  detail: string;
  error: string;
}

export interface BootstrapStatus {
  mode: "development" | "runtime";
  core: PhaseStatus;
  separation: PhaseStatus;
  torch: string | null;
}

const done: PhaseStatus = {
  state: "done",
  step: "",
  index: 0,
  total: 0,
  fraction: null,
  detail: "",
  error: "",
};

/**
 * Outside the desktop app (browser development) there is nothing to install.
 * `separationInstalled` turns true when phase B finishes during this session,
 * so the sidebar can say so instead of just hiding its indicator.
 */
export const bootstrap = $state<{
  status: BootstrapStatus;
  separationInstalled: boolean;
}>({
  status: {
    mode: "development",
    core: { ...done },
    separation: { ...done },
    torch: null,
  },
  separationInstalled: false,
});

const STEP_LABELS: Record<string, MessageKey> = {
  python: "bootstrap.step.python",
  venv: "bootstrap.step.venv",
  engine: "bootstrap.step.engine",
  ffmpeg: "bootstrap.step.ffmpeg",
  deno: "bootstrap.step.deno",
  separation: "bootstrap.step.separation",
};

export function stepLabel(step: string): MessageKey | null {
  return STEP_LABELS[step] ?? null;
}

/** Overall progress of a phase in [0, 1], counting the current download. */
export function phaseProgress(phase: PhaseStatus): number | null {
  if (phase.state === "done") return 1;
  if (phase.total === 0) return null;
  const within = phase.fraction ?? 0;
  return Math.min(1, (phase.index - 1 + within) / phase.total);
}

/** True when models can be installed and jobs can run. */
export function separationReady(status: BootstrapStatus): boolean {
  return status.mode === "development" || status.separation.state === "done";
}

/** True when this update is phase B finishing (running or failed -> done). */
export function justInstalled(
  previous: BootstrapStatus,
  next: BootstrapStatus,
): boolean {
  return (
    next.mode === "runtime" &&
    previous.separation.state !== "done" &&
    previous.separation.state !== "pending" &&
    next.separation.state === "done"
  );
}

/** True while the core runtime is missing: the UI shows the setup screen. */
export function needsSetup(status: BootstrapStatus): boolean {
  return status.mode === "runtime" && status.core.state !== "done";
}

export async function startBootstrapWatch(): Promise<void> {
  const [{ invoke }, { listen }] = await Promise.all([
    import("@tauri-apps/api/core"),
    import("@tauri-apps/api/event"),
  ]);
  await listen<BootstrapStatus>("bootstrap", (event) => {
    if (justInstalled(bootstrap.status, event.payload)) {
      bootstrap.separationInstalled = true;
    }
    bootstrap.status = event.payload;
  });
  bootstrap.status = await invoke<BootstrapStatus>("bootstrap_status");
}

export async function retryBootstrap(): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("bootstrap_retry");
}
