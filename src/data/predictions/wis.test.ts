import { describe, expect, it } from "vitest";
import type { IntervalPair, QuantileForecastPoint } from "./quantile";
import {
  coverageRates,
  intervalScore,
  isCovered,
  meanWIS,
  scoreForecasts,
  weightedIntervalScore
} from "./wis";

const pair = (alpha: number, lower: number, upper: number): IntervalPair => ({
  alpha,
  intervalWidth: 1 - alpha,
  lowerQuantile: alpha / 2,
  upperQuantile: 1 - alpha / 2,
  lowerValue: lower,
  upperValue: upper
});

describe("intervalScore", () => {
  it("returns the interval width when observed falls inside", () => {
    expect(intervalScore(10, 8, 12, 0.5)).toBe(4);
  });

  it("penalizes below the lower bound by (2/α)(l - y)", () => {
    // l=8, u=12, y=6, α=0.5 → 4 + (2/0.5)*(8-6) = 4 + 8 = 12
    expect(intervalScore(6, 8, 12, 0.5)).toBe(12);
  });

  it("penalizes above the upper bound by (2/α)(y - u)", () => {
    // l=8, u=12, y=14, α=0.5 → 4 + (2/0.5)*(14-12) = 4 + 8 = 12
    expect(intervalScore(14, 8, 12, 0.5)).toBe(12);
  });

  it("scales penalty inversely with α (95% intervals punish miss harder)", () => {
    expect(intervalScore(0, 8, 12, 0.05)).toBe(4 + (2 / 0.05) * 8);
  });
});

describe("weightedIntervalScore", () => {
  it("with no intervals reduces to absolute median error", () => {
    // (1/(0+0.5)) * 0.5 * |y - m| = |y - m|
    expect(weightedIntervalScore(15, 10, [])).toBe(5);
  });

  it("matches Bracher 2021 formula on a single 50% interval", () => {
    // α=0.5, l=8, u=12, m=10, y=10 (point + perfect coverage)
    // medianTerm = 0.5 * 0 = 0
    // intervalSum = (0.5/2) * IS = 0.25 * 4 = 1
    // WIS = (0 + 1) / (1 + 0.5) = 2/3
    const wis = weightedIntervalScore(10, 10, [pair(0.5, 8, 12)]);
    expect(wis).toBeCloseTo(2 / 3);
  });

  it("aggregates median-term and interval-terms across multiple intervals", () => {
    // y=12, m=10. Intervals:
    //   50% (α=0.5, l=8, u=12)  → IS = 4 (in)
    //   80% (α=0.2, l=6, u=14)  → IS = 8 (in)
    //   95% (α=0.05, l=4, u=16) → IS = 12 (in)
    // medianTerm = 0.5 * 2 = 1
    // intervalSum = (0.5/2)*4 + (0.2/2)*8 + (0.05/2)*12 = 1 + 0.8 + 0.3 = 2.1
    // WIS = (1 + 2.1) / (3 + 0.5) = 3.1 / 3.5
    const wis = weightedIntervalScore(12, 10, [
      pair(0.5, 8, 12),
      pair(0.2, 6, 14),
      pair(0.05, 4, 16)
    ]);
    expect(wis).toBeCloseTo(3.1 / 3.5);
  });
});

describe("isCovered", () => {
  it("inclusive at the bounds", () => {
    expect(isCovered(10, 10, 12)).toBe(true);
    expect(isCovered(12, 10, 12)).toBe(true);
    expect(isCovered(9.99, 10, 12)).toBe(false);
    expect(isCovered(12.01, 10, 12)).toBe(false);
  });
});

describe("scoreForecasts + coverageRates + meanWIS", () => {
  it("scores only forecast points with both observed and a usable median", () => {
    const forecasts = new Map<string, QuantileForecastPoint>([
      ["a", { date: "a", point: 10, quantiles: new Map([[0.25, 8], [0.75, 12]]) }],
      ["b", { date: "b", point: null, quantiles: new Map() }],
      ["c", { date: "c", point: 5, quantiles: new Map() }]
    ]);
    const truth = new Map<string, number>([
      ["a", 10],
      ["b", 1],
      ["d", 99]
    ]);
    const scored = scoreForecasts(forecasts, truth);
    expect(scored.map((s) => s.date)).toEqual(["a"]);
  });

  it("aggregates coverage per interval width and computes meanWIS", () => {
    const forecasts = new Map<string, QuantileForecastPoint>([
      [
        "2024-01-01",
        { date: "2024-01-01", point: 10, quantiles: new Map([[0.25, 8], [0.75, 12]]) }
      ],
      [
        "2024-01-02",
        { date: "2024-01-02", point: 10, quantiles: new Map([[0.25, 8], [0.75, 12]]) }
      ]
    ]);
    const truth = new Map<string, number>([
      ["2024-01-01", 10], // inside 50% interval
      ["2024-01-02", 20] // outside
    ]);
    const scored = scoreForecasts(forecasts, truth);
    const cov = coverageRates(scored);
    expect(cov).toHaveLength(1);
    expect(cov[0].intervalWidth).toBe(0.5);
    expect(cov[0].count).toBe(2);
    expect(cov[0].empiricalRate).toBeCloseTo(0.5);
    const m = meanWIS(scored);
    expect(m).not.toBeNull();
    expect(m!).toBeGreaterThan(0);
  });

  it("meanWIS returns null when no forecasts are scored", () => {
    expect(meanWIS([])).toBeNull();
  });
});
