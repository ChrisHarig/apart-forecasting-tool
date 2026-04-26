import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the JSON module before importing the loader so we don't pay the
// 2 MB parse in the test runner. Vitest hoists vi.mock to the top.
vi.mock("../../assets/geojson/admin1-50m.geo.json", () => ({
  default: {
    type: "FeatureCollection",
    features: [
      // Two GB regions
      {
        type: "Feature",
        properties: { iso_3166_2: "GB-ENG", iso_a2: "GB", name: "England", admin: "United Kingdom" },
        geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }
      },
      {
        type: "Feature",
        properties: { iso_3166_2: "GB-SCT", iso_a2: "GB", name: "Scotland", admin: "United Kingdom" },
        geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }
      },
      // Two CA regions
      {
        type: "Feature",
        properties: { iso_3166_2: "CA-AB", iso_a2: "CA", name: "Alberta", admin: "Canada" },
        geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }
      },
      {
        type: "Feature",
        properties: { iso_3166_2: "CA-ON", iso_a2: "CA", name: "Ontario", admin: "Canada" },
        geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }
      },
      // Feature without iso_3166_2 — should be filtered out by loadAll
      {
        type: "Feature",
        properties: { iso_3166_2: "", iso_a2: "ZZ", name: "Bad", admin: "Nowhere" },
        geometry: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] }
      }
    ]
  }
}));

import { _resetIso3166_2CachesForTests, loadIso3166_2GeoJson } from "./iso3166_2";

describe("loadIso3166_2GeoJson", () => {
  beforeEach(() => {
    _resetIso3166_2CachesForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("filters to features whose iso_3166_2 starts with the requested countries", async () => {
    const fc = await loadIso3166_2GeoJson(new Set(["GB"]));
    const ids = fc.features.map((f) => f.properties.id).sort();
    expect(ids).toEqual(["GB-ENG", "GB-SCT"]);
  });

  it("multi-country filter returns the union", async () => {
    const fc = await loadIso3166_2GeoJson(new Set(["GB", "CA"]));
    const ids = fc.features.map((f) => f.properties.id).sort();
    expect(ids).toEqual(["CA-AB", "CA-ON", "GB-ENG", "GB-SCT"]);
  });

  it("drops features without an iso_3166_2 code", async () => {
    const fc = await loadIso3166_2GeoJson(new Set(["GB"]));
    expect(fc.features.every((f) => f.properties.id.length > 0)).toBe(true);
  });

  it("preserves the name property reshaped into BoundaryFeatureProperties", async () => {
    const fc = await loadIso3166_2GeoJson(new Set(["GB"]));
    const england = fc.features.find((f) => f.properties.id === "GB-ENG");
    expect(england?.properties.name).toBe("England");
  });

  it("returns the same object reference on a repeat call with the same country-set (filter cache)", async () => {
    const a = await loadIso3166_2GeoJson(new Set(["GB"]));
    const b = await loadIso3166_2GeoJson(new Set(["GB"]));
    expect(a).toBe(b); // same reference, no re-filter
  });

  it("treats country-set order as irrelevant for cache hits", async () => {
    const a = await loadIso3166_2GeoJson(new Set(["GB", "CA"]));
    const b = await loadIso3166_2GeoJson(new Set(["CA", "GB"]));
    expect(a).toBe(b);
  });

  it("returns different references for different country-sets", async () => {
    const gb = await loadIso3166_2GeoJson(new Set(["GB"]));
    const ca = await loadIso3166_2GeoJson(new Set(["CA"]));
    expect(gb).not.toBe(ca);
  });

  it("empty country-set returns the full collection", async () => {
    const fc = await loadIso3166_2GeoJson(new Set());
    expect(fc.features.length).toBe(4); // the 4 valid features (bad iso_3166_2 dropped)
  });
});
