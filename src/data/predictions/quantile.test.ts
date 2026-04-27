import { describe, expect, it } from "vitest";
import { buildQuantileForecasts, findIntervalPairs } from "./quantile";

describe("buildQuantileForecasts", () => {
  it("treats point-only CSVs (no quantile column) as point estimates", () => {
    const rows = [
      { date: "2024-01-01", value: 10 },
      { date: "2024-01-08", value: 12 }
    ];
    const out = buildQuantileForecasts(rows, "date", "value", null);
    expect(out.size).toBe(2);
    expect(out.get("2024-01-01")?.point).toBe(10);
    expect(out.get("2024-01-01")?.quantiles.size).toBe(0);
  });

  it("groups long-format quantile rows by date", () => {
    const rows = [
      { date: "2024-01-01", quantile: 0.025, value: 5 },
      { date: "2024-01-01", quantile: 0.5, value: 10 },
      { date: "2024-01-01", quantile: 0.975, value: 15 }
    ];
    const out = buildQuantileForecasts(rows, "date", "value", "quantile");
    const e = out.get("2024-01-01")!;
    expect(e.quantiles.get(0.025)).toBe(5);
    expect(e.quantiles.get(0.5)).toBe(10);
    expect(e.quantiles.get(0.975)).toBe(15);
  });

  it("uses the quantile=null row as the point estimate", () => {
    const rows = [
      { date: "2024-01-01", quantile: null, value: 10 },
      { date: "2024-01-01", quantile: 0.5, value: 11 }
    ];
    const out = buildQuantileForecasts(rows, "date", "value", "quantile");
    expect(out.get("2024-01-01")?.point).toBe(10);
  });

  it("falls back to q=0.5 as the point when no null-quantile row exists", () => {
    const rows = [
      { date: "2024-01-01", quantile: 0.5, value: 11 },
      { date: "2024-01-01", quantile: 0.025, value: 5 }
    ];
    const out = buildQuantileForecasts(rows, "date", "value", "quantile");
    expect(out.get("2024-01-01")?.point).toBe(11);
  });

  it("averages multiple point rows for the same date", () => {
    const rows = [
      { date: "2024-01-01", quantile: null, value: 10 },
      { date: "2024-01-01", quantile: null, value: 20 }
    ];
    const out = buildQuantileForecasts(rows, "date", "value", "quantile");
    expect(out.get("2024-01-01")?.point).toBe(15);
  });

  it("strips time-of-day from ISO timestamps", () => {
    const rows = [{ date: "2024-01-01T12:00:00Z", quantile: 0.5, value: 10 }];
    const out = buildQuantileForecasts(rows, "date", "value", "quantile");
    expect(out.has("2024-01-01")).toBe(true);
  });

  it("ignores rows with non-numeric values", () => {
    const rows = [
      { date: "2024-01-01", quantile: 0.5, value: "n/a" },
      { date: "2024-01-01", quantile: 0.025, value: 5 }
    ];
    const out = buildQuantileForecasts(rows, "date", "value", "quantile");
    const e = out.get("2024-01-01")!;
    expect(e.quantiles.has(0.5)).toBe(false);
    expect(e.quantiles.get(0.025)).toBe(5);
  });
});

describe("findIntervalPairs", () => {
  it("produces 50/80/95 pairs from canonical quantiles", () => {
    const q = new Map<number, number>([
      [0.025, 5],
      [0.1, 7],
      [0.25, 9],
      [0.5, 10],
      [0.75, 11],
      [0.9, 13],
      [0.975, 15]
    ]);
    const pairs = findIntervalPairs(q);
    const widths = pairs.map((p) => p.intervalWidth).sort((a, b) => a - b);
    expect(widths).toEqual([0.5, 0.8, 0.95]);
    const fifty = pairs.find((p) => p.intervalWidth === 0.5)!;
    expect(fifty.lowerValue).toBe(9);
    expect(fifty.upperValue).toBe(11);
    expect(fifty.alpha).toBeCloseTo(0.5);
  });

  it("skips a quantile with no symmetric partner", () => {
    const q = new Map<number, number>([
      [0.025, 5],
      [0.5, 10],
      [0.95, 13] // partner 0.05 missing
    ]);
    const pairs = findIntervalPairs(q);
    expect(pairs).toHaveLength(0);
  });

  it("does not pair the median with itself", () => {
    const q = new Map<number, number>([[0.5, 10]]);
    expect(findIntervalPairs(q)).toEqual([]);
  });
});
