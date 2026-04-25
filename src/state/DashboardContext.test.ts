import { describe, expect, it } from "vitest";
import { SIDE_NAV_ITEMS } from "../components/Navigation/SideNav";
import { applyCountrySelection, DEFAULT_SELECTED_COUNTRY } from "./DashboardContext";
import type { SelectedCountry } from "../types/dashboard";
import dashboardShellSource from "../components/Layout/DashboardShell.tsx?raw";
import worldMapSource from "../components/Map/WorldMap.tsx?raw";
import sideNavSource from "../components/Navigation/SideNav.tsx?raw";
import sourcesPageSource from "../components/Sources/SourcesPage.tsx?raw";
import timeSeriesPageSource from "../components/TimeSeries/TimeSeriesPage.tsx?raw";
import uploadDatasetPanelSource from "../components/TimeSeries/UploadDatasetPanel.tsx?raw";

function componentSourceText() {
  return [
    dashboardShellSource,
    worldMapSource,
    sideNavSource,
    sourcesPageSource,
    timeSeriesPageSource,
    uploadDatasetPanelSource
  ].join("\n");
}

describe("dashboard country selection behavior", () => {
  it("defaults the selected country to United States", () => {
    expect(DEFAULT_SELECTED_COUNTRY).toEqual({
      iso3: "USA",
      isoNumeric: "840",
      name: "United States"
    });
  });

  it("selects a clicked country without changing the current view", () => {
    const canada: SelectedCountry = { iso3: "CAN", isoNumeric: "124", name: "Canada" };

    expect(applyCountrySelection("world", canada)).toEqual({
      view: "world",
      selectedCountry: canada
    });
    expect(applyCountrySelection("timeseries", canada)).toEqual({
      view: "timeseries",
      selectedCountry: canada
    });
  });

  it("replaces the previous selected country with the new selected country", () => {
    const france: SelectedCountry = { iso3: "FRA", isoNumeric: "250", name: "France" };
    const next = applyCountrySelection("world", france);

    expect(next.selectedCountry).toEqual(france);
    expect(next.selectedCountry).not.toEqual(DEFAULT_SELECTED_COUNTRY);
  });

  it("keeps primary navigation limited to the three expected items", () => {
    expect(SIDE_NAV_ITEMS.map((item) => item.label)).toEqual(["World Dashboard", "Sources", "Time Series"]);
  });

  it("does not render a country selector dropdown contract in the map or shell", () => {
    const sourceText = `${worldMapSource}\n${dashboardShellSource}`;

    expect(sourceText.toLowerCase()).not.toContain("country selector");
    expect(sourceText.toLowerCase()).not.toContain("selected geography");
  });

  it("does not include removed floating map copy in visible component source", () => {
    const sourceText = componentSourceText().toLowerCase();
    const removedCopy = [
      "click country to inspect sources",
      "click a country to inspect sources",
      "aggregate only",
      "baseline tiles unavailable",
      "basemap tiles are unavailable",
      "hover over country",
      "move over a country"
    ];

    removedCopy.forEach((copy) => expect(sourceText).not.toContain(copy));
  });

  it("does not include synthetic simulator or fake-risk language in visible component source", () => {
    const sourceText = componentSourceText().toLowerCase();
    ["synthetic", "rt-style", "r0", "risk score", "fake risk", "fake forecast"].forEach((copy) =>
      expect(sourceText).not.toContain(copy)
    );
  });
});
