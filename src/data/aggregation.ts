// Shared aggregation helpers used by both the time-series and seasonal
// chart modes in `src/components/Graph/`. Pure functions, no React.

import type { ValueColumn } from "../types/source";

export type AggregationMethod = "sum" | "mean" | "max" | "min" | "count";

/**
 * Map the schema's declared aggregation onto a function we know how to
 * apply here. `rate` and `proportion` don't have a clean unweighted-mean
 * story (they want population-weighted averaging which the dashboard
 * doesn't carry) so they fall back to mean — best-effort.
 */
export function pickAggregation(meta: ValueColumn | undefined): AggregationMethod {
  switch (meta?.aggregation) {
    case "sum":
    case "count":
      return "sum";
    case "max":
      return "max";
    case "mean":
    case "rate":
    case "proportion":
      return "mean";
    case "none":
    default:
      return "mean";
  }
}

export function aggregate(values: number[], method: AggregationMethod): number {
  if (values.length === 0) return NaN;
  switch (method) {
    case "sum":
      return values.reduce((a, b) => a + b, 0);
    case "max":
      return values.reduce((a, b) => (b > a ? b : a), -Infinity);
    case "min":
      return values.reduce((a, b) => (b < a ? b : a), Infinity);
    case "count":
      return values.length;
    case "mean":
    default:
      return values.reduce((a, b) => a + b, 0) / values.length;
  }
}

/**
 * Display label for the aggregation method, used in chart toolbars.
 * Falls back to the declared aggregation name when the schema gave us
 * something more specific than the executed method (e.g. "rate" → still
 * computed as mean, but the user wants to see "rate" in the meta strip).
 */
export function aggregationLabel(method: AggregationMethod, declared: ValueColumn["aggregation"] | undefined): string {
  if (declared && declared !== "none") return declared;
  return method === "sum" ? "sum" : "mean";
}
