/**
 * Hands inputs from another page (Library, CC sources) to the New job page,
 * which picks them up when it mounts.
 */
import { goto } from "$app/navigation";
import { resolve } from "$app/paths";

export const handoff = $state<{ inputs: string[] }>({ inputs: [] });

export function sendToNewJob(inputs: string[]): void {
  const merged = [...handoff.inputs];
  for (const input of inputs) if (!merged.includes(input)) merged.push(input);
  handoff.inputs = merged;
  void goto(resolve("/"));
}

/** Inputs waiting for the New job page; clears them. */
export function takeHandoff(): string[] {
  const inputs = handoff.inputs;
  handoff.inputs = [];
  return inputs;
}
