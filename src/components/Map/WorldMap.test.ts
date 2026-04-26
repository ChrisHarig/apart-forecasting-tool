import { describe, expect, it } from "vitest";
import worldMapSource from "./WorldMap.tsx?raw";

describe("WorldMap layer styling", () => {
  it("does not draw persistent country boundary or selected outline line layers over the basemap", () => {
    expect(worldMapSource).not.toContain("sentinel-country-hover-line");
    expect(worldMapSource).not.toContain("sentinel-selected-country-line");
  });

  it("keeps a subtle country boundary line only for the fallback style", () => {
    expect(worldMapSource).toContain("sentinel-fallback-country-line");
    expect(worldMapSource).toContain("if (fallbackApplied)");
  });

  it("disables world copies so selected antimeridian countries do not repeat across the viewport", () => {
    expect(worldMapSource).toContain("renderWorldCopies: false");
  });
});
