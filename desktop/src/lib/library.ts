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
