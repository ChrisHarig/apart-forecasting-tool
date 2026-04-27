import type { IntervalPair, QuantileForecastPoint } from "./quantile";
import { findIntervalPairs } from "./quantile";

// Bracher et al. 2021 ("Evaluating epidemic forecasts in an interval format")
// — interval score, weighted interval score, and per-interval coverage.
// Convention: alpha is the central interval level, so a (1-alpha) interval
// is bounded by the (alpha/2)- and (1-alpha/2)-quantiles. K = number of
// intervals; the weighted score normalizes by (K + 0.5) so WIS converges
// to CRPS as the quantile grid densifies.

export function intervalScore(
  observed: number,
  lower: number,
  upper: number,
  alpha: number
): number {
  const range = upper - lower;
  if (observed < lower) return range + (2 / alpha) * (lower - observed);
  if (observed > upper) return range + (2 / alpha) * (observed - upper);
  return range;
}

export function weightedIntervalScore(
  observed: number,
  median: number,
  pairs: IntervalPair[]
): number {
  const K = pairs.length;
  const medianTerm = 0.5 * Math.abs(observed - median);
  let intervalSum = 0;
  for (const p of pairs) {
    intervalSum += (p.alpha / 2) * intervalScore(observed, p.lowerValue, p.upperValue, p.alpha);
  }
  return (medianTerm + intervalSum) / (K + 0.5);
}

export function isCovered(observed: number, lower: number, upper: number): boolean {
  return observed >= lower && observed <= upper;
}

export interface ScoredForecast {
  date: string;
  observed: number;
  median: number;
  wis: number;
  pairs: IntervalPair[];
}

// Score every forecast point that has both an observed truth and a usable
// median/point. Returns one ScoredForecast per (date, observed, median)
// triple plus the per-row interval pairs (for downstream coverage calc).
export function scoreForecasts(
  forecasts: Map<string, QuantileForecastPoint>,
  truthByDate: Map<string, number>
): ScoredForecast[] {
  const out: ScoredForecast[] = [];
  for (const [date, fc] of forecasts) {
    const observed = truthByDate.get(date);
    if (observed === undefined || !Number.isFinite(observed)) continue;
    if (fc.point === null) continue;
    const pairs = findIntervalPairs(fc.quantiles);
    out.push({
      date,
      observed,
      median: fc.point,
      wis: weightedIntervalScore(observed, fc.point, pairs),
      pairs
    });
  }
  return out;
}

export function meanWIS(scored: ScoredForecast[]): number | null {
  if (scored.length === 0) return null;
  let sum = 0;
  for (const s of scored) sum += s.wis;
  return sum / scored.length;
}

export interface CoverageStat {
  intervalWidth: number; // e.g. 0.5 / 0.8 / 0.95
  alpha: number;
  empiricalRate: number; // [0, 1]
  count: number;
}

// Bucket coverage hits by interval width across all scored rows. Rows that
// don't carry the pair simply don't contribute to that bucket.
export function coverageRates(scored: ScoredForecast[]): CoverageStat[] {
  const buckets = new Map<number, { hits: number; n: number; alpha: number }>();
  for (const s of scored) {
    for (const p of s.pairs) {
      const key = round3(p.intervalWidth);
      const b = buckets.get(key) ?? { hits: 0, n: 0, alpha: p.alpha };
      b.n += 1;
      if (isCovered(s.observed, p.lowerValue, p.upperValue)) b.hits += 1;
      buckets.set(key, b);
    }
  }
  return Array.from(buckets.entries())
    .map(([intervalWidth, { hits, n, alpha }]) => ({
      intervalWidth,
      alpha,
      empiricalRate: n === 0 ? 0 : hits / n,
      count: n
    }))
    .sort((a, b) => a.intervalWidth - b.intervalWidth);
}

function round3(x: number): number {
  return Math.round(x * 1000) / 1000;
}
