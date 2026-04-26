import { describe, expect, it } from "vitest";
import {
  expandSyntheticToBoundaryIds,
  pickSyntheticTargetKind,
  SYNTHETIC_BOUNDARY_MAP
} from "./syntheticBoundary";

describe("expandSyntheticToBoundaryIds", () => {
  it("maps a us-state synthetic to the single FIPS", () => {
    expect(expandSyntheticToBoundaryIds("US-FLUSURV-CA", "us-state")).toEqual(["06"]);
    expect(expandSyntheticToBoundaryIds("US-METRO-AUSTIN", "us-state")).toEqual(["48"]);
  });

  it("maps a us-state-set synthetic to its full member-state list", () => {
    // HHS Region 1: CT ME MA NH RI VT
    expect(expandSyntheticToBoundaryIds("US-HHS-1", "us-state")).toEqual([
      "09",
      "23",
      "25",
      "33",
      "44",
      "50"
    ]);
  });

  it("collapses sub-state catchments onto their containing state", () => {
    // NY-Albany and NY-Rochester both paint onto NY (FIPS 36) — honest about
    // the sub-state grain loss; user's location_name in the breakdown stays.
    expect(expandSyntheticToBoundaryIds("US-FLUSURV-NY-ALBANY", "us-state")).toEqual(["36"]);
    expect(expandSyntheticToBoundaryIds("US-FLUSURV-NY-ROCHESTER", "us-state")).toEqual(["36"]);
  });

  it("returns [] when the target kind is us-state but the registry says country", () => {
    // FluSurv network-wide aggregate is `country: US`, not a state.
    expect(expandSyntheticToBoundaryIds("US-FLUSURV-ALL", "us-state")).toEqual([]);
  });

  it("returns the country ISO-2 for country-target codes", () => {
    expect(expandSyntheticToBoundaryIds("US-FLUSURV-ALL", "country")).toEqual(["US"]);
  });

  it("returns [] for codes not in the registry", () => {
    expect(expandSyntheticToBoundaryIds("US-METRO-DOES-NOT-EXIST", "us-state")).toEqual([]);
    expect(expandSyntheticToBoundaryIds("XX-UNKNOWN", "us-state")).toEqual([]);
  });
});

describe("pickSyntheticTargetKind", () => {
  it("returns 'us-state' when every code maps to a state or state-set", () => {
    const ids = new Set([
      "US-FLUSURV-CA",
      "US-FLUSURV-CO",
      "US-HHS-1" // state-set still counts as us-state-like
    ]);
    expect(pickSyntheticTargetKind(ids)).toBe("us-state");
  });

  it("returns 'country' when every code maps to a country", () => {
    const ids = new Set(["US-FLUSURV-ALL"]);
    expect(pickSyntheticTargetKind(ids)).toBe("country");
  });

  it("picks us-state when codes mix us-state and country (granularity wins)", () => {
    // delphi-flusurv has 13 catchments (us-state target) + US-FLUSURV-ALL
    // (country target). The country-target code drops out at render time;
    // user can switch to the synthesized country-aggregated level to see it.
    const ids = new Set(["US-FLUSURV-CA", "US-FLUSURV-ALL"]);
    expect(pickSyntheticTargetKind(ids)).toBe("us-state");
  });

  it("falls back to country only when no us-state-like codes are present", () => {
    const ids = new Set(["US-FLUSURV-ALL"]);
    expect(pickSyntheticTargetKind(ids)).toBe("country");
  });

  it("ignores unmapped codes when other codes resolve cleanly", () => {
    // A new metro the registry hasn't picked up yet shouldn't break the
    // render for the rest of the dataset.
    const ids = new Set(["US-HHS-1", "US-METRO-DOES-NOT-EXIST"]);
    expect(pickSyntheticTargetKind(ids)).toBe("us-state");
  });

  it("returns null only when every code is unmapped", () => {
    const ids = new Set(["US-METRO-DOES-NOT-EXIST", "US-METRO-ALSO-FAKE"]);
    expect(pickSyntheticTargetKind(ids)).toBeNull();
  });

  it("returns null on empty input", () => {
    expect(pickSyntheticTargetKind(new Set())).toBeNull();
  });
});

describe("SYNTHETIC_BOUNDARY_MAP coverage", () => {
  it("covers all 10 US HHS regions", () => {
    for (let i = 1; i <= 10; i++) {
      const code = `US-HHS-${i}`;
      const target = SYNTHETIC_BOUNDARY_MAP[code];
      expect(target, `missing ${code}`).toBeDefined();
      expect(target.kind).toBe("us-state-set");
    }
  });

  it("covers every published FluSurv-NET catchment", () => {
    const expected = [
      "US-FLUSURV-CA",
      "US-FLUSURV-CO",
      "US-FLUSURV-CT",
      "US-FLUSURV-GA",
      "US-FLUSURV-MD",
      "US-FLUSURV-MI",
      "US-FLUSURV-MN",
      "US-FLUSURV-NM",
      "US-FLUSURV-NY-ALBANY",
      "US-FLUSURV-NY-ROCHESTER",
      "US-FLUSURV-OR",
      "US-FLUSURV-TN",
      "US-FLUSURV-UT",
      "US-FLUSURV-ALL"
    ];
    for (const code of expected) {
      expect(SYNTHETIC_BOUNDARY_MAP[code], `missing ${code}`).toBeDefined();
    }
  });

  it("HHS region member-states are all valid 2-digit FIPS", () => {
    for (const [code, target] of Object.entries(SYNTHETIC_BOUNDARY_MAP)) {
      if (target.kind !== "us-state-set") continue;
      for (const fips of target.fips) {
        expect(fips, `${code} has invalid FIPS '${fips}'`).toMatch(/^\d{2}$/);
      }
    }
  });
});
