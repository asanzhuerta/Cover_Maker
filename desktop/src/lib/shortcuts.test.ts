import { describe, expect, it } from "vitest";
import { SEEK_SECONDS, shortcutFor, typingIn } from "./shortcuts";

const element = (tagName: string, extra: Record<string, unknown> = {}) =>
  ({
    tagName,
    getAttribute: (name: string) =>
      name === "role" ? ((extra.role as string) ?? null) : null,
    ...extra,
  }) as unknown as EventTarget;

const press = (key: string, target: EventTarget | null = null, more = {}) =>
  shortcutFor({ key, target, ...more });

describe("shortcuts", () => {
  it("maps the player and mixer keys", () => {
    expect(press(" ")).toEqual({ action: "play" });
    expect(press("m")).toEqual({ action: "mute" });
    expect(press("S")).toEqual({ action: "solo" });
    expect(press("3")).toEqual({ action: "lane", index: 2 });
    expect(press("7")).toBeNull();
    expect(press("l")).toEqual({ action: "loop" });
    expect(press("a")).toEqual({ action: "ab" });
    expect(press("ArrowLeft")).toEqual({
      action: "seek",
      seconds: -SEEK_SECONDS,
    });
    expect(press("ArrowDown")).toEqual({ action: "laneBy", step: 1 });
    expect(press("?")).toEqual({ action: "help" });
  });

  it("leaves keys with modifiers to the system", () => {
    expect(press("s", null, { ctrlKey: true })).toBeNull();
    expect(press("a", null, { metaKey: true })).toBeNull();
  });

  it("does nothing while the user types in a field", () => {
    for (const target of [
      element("INPUT", { type: "text" }),
      element("INPUT", { type: "search" }),
      element("TEXTAREA"),
      element("SELECT"),
      element("DIV", { isContentEditable: true }),
    ]) {
      expect(press("m", target)).toBeNull();
      expect(press(" ", target)).toBeNull();
    }
  });

  it("lets sliders keep their arrows and buttons their Space", () => {
    const range = element("INPUT", { type: "range" });
    const knob = element("DIV", { role: "slider" });
    const button = element("BUTTON");
    expect(typingIn(range, "ArrowLeft")).toBe(true);
    expect(press("ArrowRight", knob)).toBeNull();
    expect(press("m", range)).toEqual({ action: "mute" });
    expect(press(" ", button)).toBeNull();
    expect(press("s", button)).toEqual({ action: "solo" });
    expect(press(" ", element("INPUT", { type: "checkbox" }))).toBeNull();
  });
});
