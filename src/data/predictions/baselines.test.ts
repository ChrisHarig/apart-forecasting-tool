import { describe, expect, it } from "vitest";
import {
  linearTrend,
  naiveLastValue,
  naiveLastWeek,
  runBaseline,
  seasonalNaive
} from "./baselines";

const truth = [
  { date: "2024-01-01", value: 10 },
  { date: "2024-01-08", value: 12 },
  { date: "2024-01-15", value: 14 },
  { date: "2024-01-22", value: 18 }
];

describe("naiveLastValue", () => {
  it("returns the most recent strictly-prior truth value", () => {
    const out = naiveLastValue(truth, ["2024-01-09", "2024-01-22", "2024-02-01"]);
    expect(out.get("2024-01-09")).toBe(12);
    expect(out.get("2024-01-22")).toBe(14); // strictly before 2024-01-22 → 2024-01-15
    expect(out.get("2024-02-01")).toBe(18);
  });

  it("skips dates with no prior truth", () => {
    const out = naiveLastValue(truth, ["2023-12-01"]);
    expect(out.has("2023-12-01")).toBe(false);
  });
});

describe("naiveLastWeek", () => {
  it("uses the truth value exactly 7 days prior", () => {
    const out = naiveLastWeek(truth, ["2024-01-15"]);
    expect(out.get("2024-01-15")).toBe(12); // truth at 2024-01-08
  });

  it("falls back to the nearest truth within ±3 days", () => {
    // Forecast at 2024-01-12 wants truth at 2024-01-05; nearest is 2024-01-08 (3 days off)
    const out = naiveLastWeek(truth, ["2024-01-12"]);
    expect(out.get("2024-01-12")).toBe(12);
  });

  it("skips when no truth within tolerance", () => {
    const out = naiveLastWeek(truth, ["2030-01-01"]);
    expect(out.has("2030-01-01")).toBe(false);
  });
});

describe("seasonalNaive", () => {
  it("uses truth ~1 year prior within ±7 days", () => {
    const yearTruth = [
      { date: "2023-01-01", value: 100 },
      { date: "2023-01-08", value: 110 }
    ];
    // Forecast at 2024-01-04 → wants 2023-01-04, nearest truth is 2023-01-01 (3 days)
    const out = seasonalNaive(yearTruth, ["2024-01-04"]);
    expect(out.get("2024-01-04")).toBe(100);
  });

  it("skips when no prior-year truth within tolerance", () => {
    const out = seasonalNaive(truth, ["2025-06-01"]);
    expect(out.has("2025-06-01")).toBe(false);
  });
});

describe("linearTrend", () => {
  it("extrapolates a linear fit from the prior window", () => {
    // Truth: y = x days since epoch with slope 1/day, intercept k.
    // 2024-01-01 (val 10), 2024-01-02 (val 11), 2024-01-03 (val 12) → slope = 1/day.
    const linear = [
      { date: "2024-01-01", value: 10 },
      { date: "2024-01-02", value: 11 },
      { date: "2024-01-03", value: 12 }
    ];
    const out = linearTrend(linear, ["2024-01-05"], 8);
    // Day 4 from anchor → 14
    expect(out.get("2024-01-05")).toBeCloseTo(14, 5);
  });

  it("skips when fewer than 2 prior truth points", () => {
    const out = linearTrend([{ date: "2024-01-01", value: 10 }], ["2024-01-08"], 8);
    expect(out.has("2024-01-08")).toBe(false);
  });

  it("uses only the last `windowSize` points", () => {
    // Long history with a level shift: first 3 points stable at 100, last 3 trending up.
    const data = [
      { date: "2024-01-01", value: 100 },
      { date: "2024-01-02", value: 100 },
      { date: "2024-01-03", value: 100 },
      { date: "2024-01-04", value: 110 },
      { date: "2024-01-05", value: 120 },
      { date: "2024-01-06", value: 130 }
    ];
    // With windowSize=3, fit only the last 3 points (110, 120, 130 — slope 10/day).
    const out = linearTrend(data, ["2024-01-08"], 3);
    // 2024-01-08 is 2 days after the last point (130) → 150.
    expect(out.get("2024-01-08")).toBeCloseTo(150, 5);
  });
});

describe("runBaseline", () => {
  it("dispatches by key", () => {
    const out = runBaseline("naive-last-value", truth, ["2024-01-22"]);
    expect(out.get("2024-01-22")).toBe(14);
  });
});
