/** Pure helpers for the Library and CC sources pages. */

export type MatchStatus = "ready" | "needs_review" | "unavailable";

/** 1536 -> "1.5 KB", using binary multiples like Explorer. */
export function formatBytes(bytes: number): string {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = unit === 0 || value >= 100 ? 0 : 1;
  return `${value.toFixed(digits)} ${units[unit]}`;
}

/** Badge tone for an item's match status. */
export function statusTone(status: string): "ok" | "warn" | "danger" | "" {
  if (status === "ready") return "ok";
  if (status === "needs_review") return "warn";
  if (status === "unavailable") return "danger";
  return "";
}

/** Inputs of the selected items that can go to a job (matched ones only). */
export function selectedInputs(
  items: { id: number; input?: string | null; status: string }[],
  selected: Set<number>,
): string[] {
  return items
    .filter((item) => selected.has(item.id) && item.status === "ready")
    .map((item) => item.input)
    .filter((input): input is string => Boolean(input));
}

/** File name of a path or the last part of a link. */
export function baseName(input: string): string {
  return input.split(/[\\/]/).filter(Boolean).pop() ?? input;
}

/** Ids of the matched items that have no exported stems yet ("only what is new"). */
export function newItemIds(
  items: { id: number; status: string }[],
  done: Record<number, string[]>,
): number[] {
  return items
    .filter((item) => item.status === "ready" && !done[item.id]?.length)
    .map((item) => item.id);
}

/** Counts of a sync result, without the zero ones, in a stable order. */
export function syncSummary(result: {
  added: number;
  removed: number;
  unchanged: number;
  needs_review: number;
  unavailable: number;
}): [keyof typeof result, number][] {
  const keys = [
    "added",
    "removed",
    "unchanged",
    "needs_review",
    "unavailable",
  ] as const;
  return keys.filter((key) => result[key] > 0).map((key) => [key, result[key]]);
}
