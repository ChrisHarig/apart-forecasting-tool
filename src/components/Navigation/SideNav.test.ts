import { describe, expect, it } from "vitest";
import { SIDE_NAV_ITEMS } from "./SideNav";

describe("side navigation", () => {
  it("exposes exactly the three primary target sections", () => {
    expect(SIDE_NAV_ITEMS).toEqual([
      { id: "world-dashboard", label: "World Dashboard" },
      { id: "sources", label: "Sources" },
      { id: "time-series", label: "Time Series" }
    ]);
  });
});
