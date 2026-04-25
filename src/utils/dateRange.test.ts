import { describe, expect, it } from "vitest";
import type { DateRangePreset, TimeSeriesRecord } from "../types/timeseries";
import { filterRecordsByDateRange, getDateRangeBounds } from "./dateRange";

const records: TimeSeriesRecord[] = [
  { sourceId: "s1", countryIso3: "USA", date: "2024-04-22", metric: "index", value: 1, unit: "index" },
  { sourceId: "s1", countryIso3: "USA", date: "2024-04-23", metric: "index", value: 2, unit: "index" },
  { sourceId: "s1", countryIso3: "USA", date: "2025-04-24", metric: "index", value: 3, unit: "index" },
  { sourceId: "s1", countryIso3: "USA", date: "2025-10-23", metric: "index", value: 4, unit: "index" },
  { sourceId: "s1", countryIso3: "USA", date: "2026-01-23", metric: "index", value: 5, unit: "index" },
  { sourceId: "s1", countryIso3: "USA", date: "2026-03-25", metric: "index", value: 6, unit: "index" },
  { sourceId: "s1", countryIso3: "USA", date: "2026-04-11", metric: "index", value: 7, unit: "index" },
  { sourceId: "s1", countryIso3: "USA", date: "2026-04-25", metric: "index", value: 8, unit: "index" }
];

describe("date range utilities", () => {
  it("supports all required preset ranges using the latest available record as the end date", () => {
    const expectedStarts: Record<Exclude<DateRangePreset, "custom">, string> = {
      "14d": "2026-04-11",
      "1m": "2026-03-25",
      "3m": "2026-01-23",
      "6m": "2025-10-23",
      "1y": "2025-04-24",
      "2y": "2024-04-23"
    };

    Object.entries(expectedStarts).forEach(([preset, start]) => {
      expect(getDateRangeBounds(records, { preset: preset as DateRangePreset })).toEqual({
        start,
        end: "2026-04-25"
      });
    });
  });

  it("filters records inclusively without fabricating missing dates", () => {
    const filtered = filterRecordsByDateRange(records, { preset: "1m" });

    expect(filtered.map((record) => record.date)).toEqual(["2026-03-25", "2026-04-11", "2026-04-25"]);
  });
});
