import { describe, expect, it } from "vitest";
import { buildSeasonalChartData } from "./SeasonalChart";
import type { PeriodKind } from "../../data/periods";

const calendarYear: PeriodKind = { kind: "calendar-year" };
const fluNorthern: PeriodKind = { kind: "flu-season", hemisphere: "northern" };

function row(date: string, value: number, extra?: Record<string, unknown>): Record<string, unknown> {
  return { date, value, ...(extra ?? {}) };
}

describe("buildSeasonalChartData", () => {
  it("buckets one row per period at the correct xIndex", () => {
    const rows = [
      row("2022-01-01", 10), // year 2022, x=0
      row("2023-01-01", 20), // year 2023, x=0
      row("2023-12-31", 30) // year 2023, x=364
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "mean",
      periodKind: calendarYear,
      activeFilters: []
    });
    expect(out.periodIds).toEqual(["2023", "2022"]); // newest first
    const x0 = out.chartData.find((r) => r.x === 0);
    expect(x0).toEqual({ x: 0, "2023": 20, "2022": 10 });
    const x364 = out.chartData.find((r) => r.x === 364);
    expect(x364).toEqual({ x: 364, "2023": 30 });
  });

  it("aggregates multiple rows landing on the same (period, xIndex)", () => {
    const rows = [
      row("2023-01-01", 10),
      row("2023-01-01", 20),
      row("2023-01-01", 30)
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "sum",
      periodKind: calendarYear,
      activeFilters: []
    });
    expect(out.chartData).toEqual([{ x: 0, "2023": 60 }]);
  });

  it("respects mean aggregation", () => {
    const rows = [
      row("2023-01-01", 10),
      row("2023-01-01", 20),
      row("2023-01-01", 30)
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "mean",
      periodKind: calendarYear,
      activeFilters: []
    });
    expect(out.chartData[0]["2023"]).toBe(20);
  });

  it("buckets flu seasons across the year boundary correctly", () => {
    const rows = [
      row("2023-10-01", 5), // start of 2023-24 season
      row("2024-01-01", 7), // 92 days into 2023-24 season
      row("2024-09-30", 9) // last day of 2023-24 season
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "sum",
      periodKind: fluNorthern,
      activeFilters: []
    });
    expect(out.periodIds).toEqual(["2023-24"]);
    const xs = out.chartData.map((r) => r.x).sort((a, b) => a - b);
    expect(xs[0]).toBe(0); // Oct 1
    expect(xs[1]).toBe(92); // Jan 1 next year
    expect(xs[2]).toBe(365); // Sep 30 next year (leap year so 366 days from Oct 1 2023)
  });

  it("filters rows by activeFilters before bucketing", () => {
    const rows = [
      row("2023-01-01", 10, { region: "north" }),
      row("2023-01-01", 20, { region: "south" }),
      row("2023-01-01", 30, { region: "south" })
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "sum",
      periodKind: calendarYear,
      activeFilters: [{ name: "region", value: "south" }]
    });
    // Only south rows: 20 + 30 = 50
    expect(out.chartData[0]["2023"]).toBe(50);
  });

  it("ignores rows where the metric value isn't a finite number", () => {
    const rows = [
      row("2023-01-01", 10),
      { date: "2023-01-01", value: null },
      { date: "2023-01-01", value: "not a number" },
      { date: "2023-01-01" } // missing value
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "sum",
      periodKind: calendarYear,
      activeFilters: []
    });
    expect(out.chartData[0]["2023"]).toBe(10);
  });

  it("ignores rows with unparseable dates", () => {
    const rows = [
      row("2023-01-01", 10),
      { date: "not-a-date", value: 99 },
      { date: "", value: 99 },
      { date: null, value: 99 }
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "sum",
      periodKind: calendarYear,
      activeFilters: []
    });
    expect(out.chartData[0]["2023"]).toBe(10);
    expect(out.periodIds).toEqual(["2023"]);
  });

  it("returns empty data when no rows pass through", () => {
    const out = buildSeasonalChartData({
      rows: [],
      dateField: "date",
      metric: "value",
      aggMethod: "sum",
      periodKind: calendarYear,
      activeFilters: []
    });
    expect(out.chartData).toEqual([]);
    expect(out.periodIds).toEqual([]);
  });

  it("orders chartData by ascending x (so Recharts draws left-to-right)", () => {
    const rows = [
      row("2023-12-31", 30),
      row("2023-01-01", 10),
      row("2023-06-01", 20)
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "sum",
      periodKind: calendarYear,
      activeFilters: []
    });
    const xs = out.chartData.map((r) => r.x);
    for (let i = 1; i < xs.length; i++) expect(xs[i]).toBeGreaterThan(xs[i - 1]);
  });

  it("produces sparse rows when periods don't share xIndex (different weekday alignment across years)", () => {
    // Saturdays land on different days-of-year across years:
    //   Sat Jan 3 2009 → day-of-year 2
    //   Sat Jan 2 2010 → day-of-year 1
    // The bucketed chartData shape must keep these as *separate* rows;
    // each row carries only the period whose date matches its xIndex.
    // SeasonalChart relies on connectNulls={true} to draw across the gaps.
    const rows = [
      row("2009-01-03", 1.0), // x=2 in 2009
      row("2010-01-02", 2.0), // x=1 in 2010
      row("2010-01-09", 3.0), // x=8 in 2010
      row("2009-01-10", 4.0) // x=9 in 2009
    ];
    const out = buildSeasonalChartData({
      rows,
      dateField: "date",
      metric: "value",
      aggMethod: "sum",
      periodKind: calendarYear,
      activeFilters: []
    });
    expect(out.periodIds.sort()).toEqual(["2009", "2010"]);
    // Each chartData row holds at most one period's value for that xIndex.
    // No row has both keys set — the keys never overlap.
    for (const r of out.chartData) {
      const present = ["2009", "2010"].filter((p) => p in r);
      expect(present.length).toBe(1);
    }
    // Each period's defined points are spread across non-adjacent xIndexes,
    // which is the case Recharts has to handle with connectNulls=true.
    const x2009 = out.chartData.filter((r) => "2009" in r).map((r) => r.x);
    const x2010 = out.chartData.filter((r) => "2010" in r).map((r) => r.x);
    expect(x2009).toEqual([2, 9]);
    expect(x2010).toEqual([1, 8]);
  });
});
