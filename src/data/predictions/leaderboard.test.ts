import { describe, expect, it } from "vitest";
import {
  aggregateTruthForScoring,
  buildSubmitterForecasts,
  computeSubmitterScores,
  dominantPredictionDimValues
} from "./leaderboard";
import { parsePredictionRows } from "./companion";

function makeRow(
  date: string,
  submitter: string,
  quantile: number | null,
  value: number,
  dim?: Record<string, string>
) {
  return {
    target_date: date,
    submitter,
    model_name: "v1",
    description: "x",
    quantile,
    value,
    ...(dim ?? {})
  };
}

describe("buildSubmitterForecasts", () => {
  it("groups rows by date and separates point + quantile values", () => {
    const rows = [
      { date: "2026-01-01", submitter: "a", modelName: "m", quantile: null, value: 100, dims: {} },
      { date: "2026-01-01", submitter: "a", modelName: "m", quantile: 0.5, value: 100, dims: {} },
      { date: "2026-01-01", submitter: "a", modelName: "m", quantile: 0.9, value: 130, dims: {} }
    ];
    const fc = buildSubmitterForecasts(rows);
    const entry = fc.get("2026-01-01")!;
    expect(entry.point).toBe(100);
    expect(entry.quantiles.get(0.5)).toBe(100);
    expect(entry.quantiles.get(0.9)).toBe(130);
  });

  it("falls back to median when no point row is present", () => {
    const rows = [
      { date: "2026-01-01", submitter: "a", modelName: "m", quantile: 0.5, value: 50, dims: {} }
    ];
    const fc = buildSubmitterForecasts(rows);
    expect(fc.get("2026-01-01")!.point).toBe(50);
  });
});

describe("aggregateTruthForScoring", () => {
  it("filters truth rows by precise named column matches", () => {
    const rows = [
      { date: "2026-01-01", location_id: "06", location_name: "CA", value: 100 },
      { date: "2026-01-01", location_id: "12", location_name: "FL", value: 50 },
      { date: "2026-01-08", location_id: "06", location_name: "CA", value: 110 }
    ];
    const truth = aggregateTruthForScoring(rows, "date", "value", {
      filters: [{ name: "location_id", value: "06" }]
    });
    expect(truth.get("2026-01-01")).toBe(100);
    expect(truth.get("2026-01-08")).toBe(110);
    expect(truth.size).toBe(2);
  });

  it("requires every filter to match (AND semantics)", () => {
    const rows = [
      { date: "2026-01-01", state: "CA", region: "west", value: 100 },
      { date: "2026-01-01", state: "CA", region: "south", value: 50 },
      { date: "2026-01-01", state: "FL", region: "west", value: 70 }
    ];
    const truth = aggregateTruthForScoring(rows, "date", "value", {
      filters: [
        { name: "state", value: "CA" },
        { name: "region", value: "west" }
      ]
    });
    expect(truth.get("2026-01-01")).toBe(100);
    expect(truth.size).toBe(1);
  });

  it("aggregates across rows with mean by default", () => {
    const rows = [
      { date: "2026-01-01", value: 100 },
      { date: "2026-01-01", value: 200 }
    ];
    expect(aggregateTruthForScoring(rows, "date", "value").get("2026-01-01")).toBe(150);
  });

  it("supports sum aggregation", () => {
    const rows = [
      { date: "2026-01-01", value: 100 },
      { date: "2026-01-01", value: 50 }
    ];
    expect(
      aggregateTruthForScoring(rows, "date", "value", { method: "sum" }).get("2026-01-01")
    ).toBe(150);
  });
});

describe("computeSubmitterScores", () => {
  it("scores each submitter against truth, ordering by submitter", () => {
    const parsed = parsePredictionRows([
      makeRow("2026-01-01", "alice", null, 100, { location: "CA" }),
      makeRow("2026-01-01", "alice", 0.5, 100, { location: "CA" }),
      makeRow("2026-01-08", "alice", null, 110, { location: "CA" }),
      makeRow("2026-01-01", "bob", null, 200, { location: "CA" }),
      makeRow("2026-01-08", "bob", null, 210, { location: "CA" })
    ]);
    const truth = new Map([
      ["2026-01-01", 100],
      ["2026-01-08", 100]
    ]);
    const scores = computeSubmitterScores(parsed, truth);
    expect(scores.map((s) => s.submitter)).toEqual(["alice", "bob"]);
    const alice = scores.find((s) => s.submitter === "alice")!;
    const bob = scores.find((s) => s.submitter === "bob")!;
    // alice predicts 100, 110 vs truth 100, 100 → MAE = (0 + 10) / 2 = 5
    expect(alice.mae).toBe(5);
    expect(alice.scoredCount).toBe(2);
    // bob predicts 200, 210 vs truth 100, 100 → MAE = (100 + 110) / 2 = 105
    expect(bob.mae).toBe(105);
    // alice (closer) should beat bob on MAE
    expect(alice.mae!).toBeLessThan(bob.mae!);
  });

  it("returns null scores for submitters with no overlap with truth", () => {
    const parsed = parsePredictionRows([
      makeRow("2099-01-01", "future", null, 1)
    ]);
    const truth = new Map([["2026-01-01", 100]]);
    const scores = computeSubmitterScores(parsed, truth);
    expect(scores[0].scoredCount).toBe(0);
    expect(scores[0].mae).toBeNull();
    expect(scores[0].wis).toBeNull();
  });
});

describe("dominantPredictionDimValues", () => {
  it("picks the majority value per dim", () => {
    const parsed = parsePredictionRows([
      makeRow("2026-01-01", "a", null, 1, { location: "CA" }),
      makeRow("2026-01-08", "a", null, 1, { location: "CA" }),
      makeRow("2026-01-15", "a", null, 1, { location: "CA" })
    ]);
    expect(dominantPredictionDimValues(parsed)).toEqual(["CA"]);
  });

  it("omits dims with no clear majority", () => {
    const parsed = parsePredictionRows([
      makeRow("2026-01-01", "a", null, 1, { location: "CA" }),
      makeRow("2026-01-08", "a", null, 1, { location: "FL" }),
      makeRow("2026-01-15", "a", null, 1, { location: "TX" })
    ]);
    expect(dominantPredictionDimValues(parsed)).toEqual([]);
  });
});
