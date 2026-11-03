/** Pure helpers to derive progress from job details and engine events. */
import type { EngineEvent } from "./connection.svelte";

export interface ItemView {
  id: number;
  input: string;
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
