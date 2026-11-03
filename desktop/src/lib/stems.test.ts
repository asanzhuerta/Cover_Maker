import { describe, expect, it } from "vitest";
import { STEMS, STEM_COLORS, stemColor, stemLabel } from "./stems";

describe("stems", () => {
  it("lists the six selectable stems", () => {
    expect(STEMS).toHaveLength(6);
  });

  it("capitalises labels", () => {
    expect(stemLabel("vocals")).toBe("Vocals");
  });

  it("gives every stem its own colour", () => {
    expect(new Set(STEMS.map((s) => STEM_COLORS[s])).size).toBe(STEMS.length);
    expect(stemColor("unknown")).toBe(STEM_COLORS.other);
  });
});
