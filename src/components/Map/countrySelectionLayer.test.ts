import { describe, expect, it } from "vitest";
import { buildCountrySelectionGeoJson } from "./countrySelectionLayer";

function maxLongitudeJump(coordinates: unknown): number {
  let maxJump = 0;

  const visit = (value: unknown) => {
    if (!Array.isArray(value)) return;
    const isRing = value.every((point) => Array.isArray(point) && typeof point[0] === "number" && typeof point[1] === "number");
    if (isRing) {
      for (let index = 1; index < value.length; index += 1) {
        maxJump = Math.max(maxJump, Math.abs(value[index][0] - value[index - 1][0]));
      }
      return;
    }
    value.forEach(visit);
  };

  visit(coordinates);
  return maxJump;
}

describe("country selection layer", () => {
  it("joins map countries through stable ISO numeric to ISO3 references", () => {
    const geoJson = buildCountrySelectionGeoJson({ USA: 4 });
    const usa = geoJson.features.find((feature) => feature.properties.iso3 === "USA");

    expect(usa?.properties).toMatchObject({
      iso3: "USA",
      isoNumeric: "840",
      name: "United States of America",
      sourceCoverageCount: 4
    });
  });

  it("unwraps country geometry at the antimeridian to avoid cross-map fill artifacts", () => {
    const geoJson = buildCountrySelectionGeoJson();
    const russia = geoJson.features.find((feature) => feature.properties.iso3 === "RUS");

    if (!russia) throw new Error("Russia should exist in the country selection layer");

    expect(russia.geometry.type).not.toBe("GeometryCollection");
    expect(maxLongitudeJump("coordinates" in russia.geometry ? russia.geometry.coordinates : [])).toBeLessThanOrEqual(180);
  });
});
