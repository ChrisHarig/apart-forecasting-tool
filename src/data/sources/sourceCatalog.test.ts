import { describe, expect, it } from "vitest";
import { orderedSourceCategories, sourceCategoryLabels } from "./sourceCategories";
import { sourceCatalog } from "./sourceCatalog";

describe("source catalog", () => {
  it("contains the required country-first source categories", () => {
    expect(orderedSourceCategories.map((category) => sourceCategoryLabels[category])).toEqual([
      "Pathogen surveillance",
      "Wastewater",
      "Forecasts / nowcasts",
      "Mobility / air travel",
      "Ports / maritime / cargo",
      "Population / demographics",
      "Open-source news / event surveillance",
      "User-added sources"
    ]);
  });

  it("includes key public-health, mobility, and maritime source entries", () => {
    const names = sourceCatalog.map((source) => source.name);

    [
      "WastewaterSCAN",
      "CDC FluSight current-week visualization",
      "CDC FluSight Forecast Hub",
      "Reich Lab FluSight dashboard",
      "CDC NWSS / wastewater program",
      "WHO FluNet",
      "OpenSky Network",
      "OurAirports",
      "IMF PortWatch / UN AIS-derived port activity",
      "NGA World Port Index (Pub. 150)",
      "USACE WCSC Navigation Facilities",
      "NOAA / BOEM Marine Cadastre AIS Vessel Traffic",
      "MARAD / BTS / USACE NTAD Principal Ports",
      "Future teammate-provided wastewater dataset",
      "Future teammate-provided mobility dataset",
      "Future teammate-provided ferry/cargo dataset",
      "Future teammate-provided population-density dataset"
    ].forEach((requiredName) => {
      expect(names).toContain(requiredName);
    });
  });

  it("marks all built-in entries as aggregate-only metadata", () => {
    expect(sourceCatalog.every((source) => source.aggregateOnly === true && source.userAdded === false)).toBe(true);
  });
});
