import { describe, expect, it } from "vitest";
import type { SourceMetadata } from "../../types/source";
import type { UserDataset } from "./types";
import { deriveAcceptableRange, validateDates } from "./validate";

const mkTarget = (start: string, end: string | "present"): SourceMetadata => ({
  id: "EPI-Eval/foo",
  pretty_name: "Foo",
  source_id: "foo",
  surveillance_category: "respiratory",
  pathogens: [],
  geography_levels: [],
  geography_countries: [],
  value_columns: [],
  computed: { time_coverage: [{ start, end }] }
});

const mkPrediction = (dates: string[]): UserDataset => ({
  id: "user-x",
  filename: "p.csv",
  uploadedAt: 0,
  rows: dates.map((d) => ({ date: d, value: 1 })),
  dateField: "date",
  numericFields: ["value"],
  quantileField: null,
  rowCount: dates.length
});

describe("deriveAcceptableRange", () => {
  it("uses start through end + ~2 months for a fixed end", () => {
    const r = deriveAcceptableRange(mkTarget("2020-01-01", "2024-01-01"));
    expect(r).not.toBeNull();
    expect(r!.min).toBe("2020-01-01");
    expect(r!.max).toBe("2024-03-01"); // 2024-01-01 + 60 days
  });

  it("uses today for `present` end", () => {
    const r = deriveAcceptableRange(mkTarget("2020-01-01", "present"));
    expect(r).not.toBeNull();
    const todayMs = Date.parse(new Date().toISOString().slice(0, 10));
    const maxMs = Date.parse(r!.max);
    const days = (maxMs - todayMs) / (24 * 60 * 60 * 1000);
    expect(days).toBeGreaterThanOrEqual(59);
    expect(days).toBeLessThanOrEqual(61);
  });

  it("returns null when coverage is missing", () => {
    const target = mkTarget("2020-01-01", "2024-01-01");
    delete target.computed!.time_coverage;
    expect(deriveAcceptableRange(target)).toBeNull();
  });
});

describe("validateDates", () => {
  const target = mkTarget("2020-01-01", "2024-01-01");

  it("passes when all dates are within range", () => {
    const pred = mkPrediction(["2020-01-01", "2024-01-15", "2024-02-15"]);
    const r = validateDates(pred, target);
    expect(r.ok).toBe(true);
    expect(r.outOfRangeRows).toEqual([]);
    expect(r.parseErrorRows).toEqual([]);
  });

  it("flags dates before coverage start", () => {
    const pred = mkPrediction(["2019-12-31", "2020-01-01"]);
    const r = validateDates(pred, target);
    expect(r.ok).toBe(false);
    expect(r.outOfRangeRows).toEqual([0]);
  });

  it("flags dates more than ~2 months past coverage end", () => {
    const pred = mkPrediction(["2024-04-01"]);
    const r = validateDates(pred, target);
    expect(r.ok).toBe(false);
    expect(r.outOfRangeRows).toEqual([0]);
  });

  it("flags unparseable dates", () => {
    const pred = mkPrediction(["not-a-date"]);
    const r = validateDates(pred, target);
    expect(r.ok).toBe(false);
    expect(r.parseErrorRows).toEqual([0]);
  });

  it("ignores time-of-day (matches on YYYY-MM-DD only)", () => {
    const pred = mkPrediction(["2020-01-01T12:00:00Z"]);
    const r = validateDates(pred, target);
    expect(r.ok).toBe(true);
  });

  it("returns ok when target has no coverage info", () => {
    const noCoverage = mkTarget("2020-01-01", "2024-01-01");
    delete noCoverage.computed!.time_coverage;
    const pred = mkPrediction(["1900-01-01"]);
    const r = validateDates(pred, noCoverage);
    expect(r.ok).toBe(true);
    expect(r.acceptedRange).toBeNull();
  });
});
