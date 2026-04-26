import { describe, expect, it } from "vitest";
import { detectBoundaryLevels, isRenderable } from "./detection";

function row(location_id: string, location_level: string): { location_id: string; location_level: string } {
  return { location_id, location_level };
}

describe("classifyId via detectBoundaryLevels", () => {
  it("classifies 5-digit FIPS as us-county", () => {
    const levels = detectBoundaryLevels([row("06037", "subnational-county")]);
    expect(levels[0].boundaryType).toBe("us-county");
  });

  it("classifies 2-digit FIPS as us-state", () => {
    const levels = detectBoundaryLevels([row("06", "subnational-state")]);
    expect(levels[0].boundaryType).toBe("us-state");
  });

  it("classifies 2-letter all-caps as country", () => {
    const levels = detectBoundaryLevels([row("BR", "national")]);
    expect(levels[0].boundaryType).toBe("country");
  });

  it("classifies ISO 3166-2 (2 segments) as iso3166-2", () => {
    const levels = detectBoundaryLevels([row("BR-SP", "subnational-state")]);
    expect(levels[0].boundaryType).toBe("iso3166-2");
  });

  it("classifies 3-segment synthetic codes as subnational-region", () => {
    // US-HHS-1 (HHS region), US-FLUSURV-CA (FluSurv catchment), BR-IBGE-12345
    // (IBGE-style sub-state code) all share the 3-segment shape.
    expect(detectBoundaryLevels([row("US-HHS-1", "subnational-region")])[0].boundaryType).toBe(
      "subnational-region"
    );
    expect(detectBoundaryLevels([row("US-FLUSURV-CA", "subnational-region")])[0].boundaryType).toBe(
      "subnational-region"
    );
    expect(detectBoundaryLevels([row("US-METRO-NYC", "subnational-city")])[0].boundaryType).toBe(
      "subnational-region"
    );
  });

  // Tier 0 fix — 4+ segment codes used to fall through to "unsupported".
  it("classifies 4-segment FluSurv catchments as subnational-region (Tier 0 fix)", () => {
    expect(
      detectBoundaryLevels([row("US-FLUSURV-NY-ALBANY", "subnational-region")])[0].boundaryType
    ).toBe("subnational-region");
    expect(
      detectBoundaryLevels([row("US-FLUSURV-NY-ROCHESTER", "subnational-region")])[0].boundaryType
    ).toBe("subnational-region");
  });

  it("classifies 5+ segment codes as subnational-region", () => {
    expect(
      detectBoundaryLevels([row("AF-METRO-KABUL-METROPOLITAN-AREA", "subnational-region")])[0]
        .boundaryType
    ).toBe("subnational-region");
  });

  it("classifies point: prefix as point", () => {
    const levels = detectBoundaryLevels([row("point:34.05,-118.24", "point")]);
    expect(levels[0].boundaryType).toBe("point");
  });

  it("classifies facility: prefix as facility", () => {
    const levels = detectBoundaryLevels([row("facility:nwss-12345", "facility")]);
    expect(levels[0].boundaryType).toBe("facility");
  });

  it("classifies WORLD as unsupported (use 'global' level + ISO-style for global rows)", () => {
    const levels = detectBoundaryLevels([row("WORLD", "global")]);
    expect(levels[0].boundaryType).toBe("unsupported");
  });

  it("buckets rows by (level, boundaryType) and counts unique ids", () => {
    const rows = [
      row("06", "subnational-state"),
      row("06", "subnational-state"),
      row("48", "subnational-state"),
      row("US", "national")
    ];
    const levels = detectBoundaryLevels(rows);
    const stateLevel = levels.find((l) => l.boundaryType === "us-state");
    expect(stateLevel?.ids.size).toBe(2);
    expect(stateLevel?.rowCount).toBe(3);
    const countryLevel = levels.find((l) => l.boundaryType === "country");
    expect(countryLevel?.rowCount).toBe(1);
  });
});

describe("isRenderable", () => {
  it("returns true for the boundary types we have polygons for", () => {
    expect(isRenderable("country")).toBe(true);
    expect(isRenderable("us-state")).toBe(true);
    expect(isRenderable("us-county")).toBe(true);
    expect(isRenderable("iso3166-2")).toBe(true);
    expect(isRenderable("subnational-region")).toBe(true);
  });

  it("returns false for boundary types without polygon support", () => {
    expect(isRenderable("point")).toBe(false);
    expect(isRenderable("facility")).toBe(false);
    expect(isRenderable("unsupported")).toBe(false);
  });
});
