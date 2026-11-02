import { describe, expect, it } from "vitest";
import { STEMS, stemLabel } from "./stems";

describe("stems", () => {
  it("lists the six selectable stems", () => {
    expect(STEMS).toHaveLength(6);
  });

  it("capitalises labels", () => {
    expect(stemLabel("vocals")).toBe("Vocals");
  });
});
