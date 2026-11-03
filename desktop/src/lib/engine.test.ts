import { describe, expect, it } from "vitest";
import { baseUrl } from "./engine";

describe("engine client", () => {
  it("targets the loopback address and announced port", () => {
    expect(baseUrl({ port: 51234, token: "t", pid: 1, version: "0" })).toBe(
      "http://127.0.0.1:51234",
    );
  });
});
