import { describe, expect, it } from "vitest";
import { _internal } from "./catalog";

describe("deriveSourceFromHf", () => {
  it("maps the EPI-Eval card schema to the SourceMetadata shape", () => {
    const source = _internal.deriveSourceFromHf({
      id: "EPI-Eval/cdc-ilinet",
      lastModified: "2026-04-20T10:00:00Z",
      cardData: {
        pretty_name: "CDC ILINet",
        source_id: "cdc-ilinet",
        source_url: "https://gis.cdc.gov/grasp/fluview",
        surveillance_category: "respiratory",
        pathogens: ["influenza"],
        cadence: "weekly",
        geography_levels: ["national", "subnational-state"],
        geography_countries: ["US"],
        tier: 1,
        availability: "open",
        access_type: "api",
        value_columns: [
          { name: "ili_pct", dtype: "float", unit: "%", value_type: "proportion" },
          { name: "n_visits", dtype: "int", value_type: "count" }
        ],
        computed: {
          row_count: 12345,
          time_coverage: [{ start: "1997-10-01", end: "present" }],
          observed_cadence_days: 7
        },
        notes: { general: "ILI sentinel network." }
      }
    });

    expect(source.id).toBe("EPI-Eval/cdc-ilinet");
    expect(source.pretty_name).toBe("CDC ILINet");
    expect(source.surveillance_category).toBe("respiratory");
    expect(source.pathogens).toEqual(["influenza"]);
    expect(source.tier).toBe(1);
    expect(source.value_columns).toHaveLength(2);
    expect(source.value_columns[0]).toMatchObject({ name: "ili_pct", dtype: "float", unit: "%", value_type: "proportion" });
    expect(source.computed?.row_count).toBe(12345);
    expect(source.computed?.time_coverage?.[0]).toEqual({ start: "1997-10-01", end: "present" });
    expect(source.notes_general).toBe("ILI sentinel network.");
  });

  it("falls back to id when card metadata is missing", () => {
    const source = _internal.deriveSourceFromHf({ id: "EPI-Eval/something-new" });
    expect(source.pretty_name).toBe("something-new");
    expect(source.surveillance_category).toBe("none");
    expect(source.value_columns).toEqual([]);
    expect(source.pathogens).toEqual([]);
  });

  it("rejects unknown surveillance categories rather than passing them through", () => {
    const source = _internal.deriveSourceFromHf({
      id: "EPI-Eval/x",
      cardData: { surveillance_category: "made-up-category" }
    });
    expect(source.surveillance_category).toBe("none");
  });
});

describe("isPredictionsCompanion", () => {
  it("identifies predictions companion repos by suffix", () => {
    expect(_internal.isPredictionsCompanion({ id: "EPI-Eval/nhsn-hrd-predictions" })).toBe(true);
    expect(_internal.isPredictionsCompanion({ id: "EPI-Eval/flusight-forecast-hub-predictions" })).toBe(true);
  });

  it("does not flag truth datasets", () => {
    expect(_internal.isPredictionsCompanion({ id: "EPI-Eval/nhsn-hrd" })).toBe(false);
    expect(_internal.isPredictionsCompanion({ id: "EPI-Eval/flusight-forecast-hub" })).toBe(false);
    // A dataset that happens to contain the substring elsewhere should still
    // be treated as truth.
    expect(_internal.isPredictionsCompanion({ id: "EPI-Eval/predictions-archive" })).toBe(false);
  });
});
