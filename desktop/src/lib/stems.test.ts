import { describe, expect, it } from "vitest";
import {
  CHOOSABLE,
  STEMS,
  STEM_COLORS,
  isStem,
  mixerStems,
  stemColor,
  stemLabel,
} from "./stems";
import { ICONS } from "./icons";
import { translate } from "./i18n.svelte";

describe("stems", () => {
  it("lists the six top-level stems", () => {
    expect(STEMS).toHaveLength(6);
  });

  it("offers lead and backing vocals right after the vocals", () => {
    expect(CHOOSABLE.slice(0, 4)).toEqual([
      "vocals",
      "vocals.lead",
      "vocals.backing",
      "guitar",
    ]);
    expect(CHOOSABLE).toHaveLength(8);
  });

  it("capitalises labels", () => {
    expect(stemLabel("vocals")).toBe("Vocals");
  });

  it("gives every stem its own colour, icon and name", () => {
    expect(new Set(CHOOSABLE.map((s) => STEM_COLORS[s])).size).toBe(
      CHOOSABLE.length,
    );
    expect(stemColor("unknown")).toBe(STEM_COLORS.other);
    for (const stem of CHOOSABLE) {
      expect(ICONS[stem]).toBeDefined();
      expect(translate("en", `stem.${stem}`)).toBeTruthy();
      expect(translate("es", `stem.${stem}`)).toBeTruthy();
    }
    expect(isStem("vocals.lead")).toBe(true);
    expect(isStem("vocals.choir")).toBe(false);
  });

  it("shows lead and backing lanes in place of the vocals", () => {
    expect(mixerStems(["bass", "vocals", "drums"])).toEqual([
      "vocals",
      "drums",
      "bass",
    ]);
    expect(
      mixerStems(["vocals.backing", "guitar", "vocals", "vocals.lead"]),
    ).toEqual(["vocals.lead", "vocals.backing", "guitar"]);
    // Half a split is not enough: the vocals stay whole.
    expect(mixerStems(["vocals", "vocals.lead"])).toEqual(["vocals"]);
  });
});
