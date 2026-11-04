import { describe, expect, it } from "vitest";
import { errorHint } from "./errors";

describe("error hints", () => {
  it("recognises the engine's common failures", () => {
    expect(
      errorHint("Cannot decode song.m4a without ffmpeg. Install ffmpeg"),
    ).toBe("hint.ffmpeg");
    expect(errorHint("ffmpeg could not decode a.wav: Invalid data")).toBe(
      "hint.decode",
    );
    expect(
      errorHint("RuntimeError: CUDA out of memory. Tried to allocate"),
    ).toBe("hint.memory");
    expect(errorHint("separation worker exited (code 3221225477)")).toBe(
      "hint.worker",
    );
    expect(
      errorHint("Separation support is not installed yet. The app installs"),
    ).toBe("hint.runtime");
    expect(errorHint("model bs-roformer-sw is not installed")).toBe(
      "hint.model",
    );
    expect(errorHint("could not download dQw4w9WgXcQ: HTTP Error 403")).toBe(
      "hint.download",
    );
    expect(errorHint("input file not found: C:\\Music\\a.wav")).toBe(
      "hint.missingFile",
    );
    expect(errorHint("asset abc is missing from the library")).toBe(
      "hint.cache",
    );
  });

  it("returns nothing for unknown or empty errors", () => {
    expect(errorHint("something unexpected")).toBeNull();
    expect(errorHint("")).toBeNull();
    expect(errorHint(null)).toBeNull();
  });
});
