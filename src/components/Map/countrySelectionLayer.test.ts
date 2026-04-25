import { describe, expect, it } from "vitest";
import { buildCountrySelectionGeoJson } from "./countrySelectionLayer";

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
});
