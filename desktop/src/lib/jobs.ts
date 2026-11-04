/** Pure helpers to derive progress from job details and engine events. */
import type { EngineEvent } from "./connection.svelte";

export interface ItemView {
  id: number;
  input: string;
  /** From the file's tags or the video's metadata; null until known. */
  title: string | null;
  artist: string | null;
  status: string;
  step: string | null;
  fraction: number | null;
  error: string | null;
  outputs: Record<string, string>;
}

/** Steps an item goes through, used for a coarse progress estimate. */
export const STEP_WEIGHTS: Record<string, number> = {
  download: 0.15,
  decode: 0.25,
  separate: 0.85,
  export: 0.95,
};

export function itemProgress(item: ItemView): number {
  if (item.status === "done") return 1;
  if (!item.step) return 0;
  const base = item.step.startsWith("separate") ? "separate" : item.step;
  const at = STEP_WEIGHTS[base] ?? 0;
  if (base === "download" && item.fraction !== null) return at * item.fraction;
  return at;
}

/** Coarse step name of an item step id, e.g. "separate:sw" -> "separate". */
export function stepName(
  step: string,
): "download" | "decode" | "separate" | "export" | null {
  const base = step.split(":")[0];
  return base === "download" ||
    base === "decode" ||
    base === "separate" ||
    base === "export"
    ? base
    : null;
}

/**
 * What "Open folder" reveals: the first exported file, so Explorer opens the
 * output folder with it selected; the output folder itself until then.
 */
export function revealTarget(outputDir: string, items: ItemView[]): string {
  for (const item of items) {
    const first = Object.values(item.outputs)[0];
    if (first) return first;
  }
  return outputDir;
}

/** What the queue shows for an item: its title, else the file name or link. */
export function itemLabel(item: ItemView): { title: string; artist: string } {
  return {
    title: item.title || displayName(item.input),
    artist: item.artist ?? "",
  };
}

export function displayName(input: string): string {
  if (/^https?:\/\//i.test(input)) return input;
  return input.split(/[\\/]/).pop() ?? input;
}

/** Apply one engine event to the item list of a job (returns a new list). */
export function applyEvent(items: ItemView[], event: EngineEvent): ItemView[] {
  const id = event.item as number | undefined;
  if (id === undefined) return items;
  return items.map((item) => {
    if (item.id !== id) return item;
    switch (event.type) {
      case "item.step":
        return {
          ...item,
          status: "running",
          step: String(event.step),
          fraction: null,
        };
      case "item.meta":
        return {
          ...item,
          title: (event.title as string | null) || null,
          artist: (event.artist as string | null) || null,
        };
      case "item.progress":
        return { ...item, fraction: (event.fraction as number | null) ?? null };
      case "item.done":
        return {
          ...item,
          status: "done",
          step: null,
          outputs: (event.outputs as Record<string, string>) ?? {},
        };
      case "item.failed":
        return {
          ...item,
          status: "failed",
          step: null,
          error: String(event.error ?? ""),
        };
      case "item.cancelled":
        return { ...item, status: "cancelled", step: null };
      default:
        return item;
    }
  });
}
