// Per-submitter scoring against truth — turns the prediction overlay into
// a leaderboard. Reuses the metric primitives built for personal uploads
// (metrics.ts / wis.ts / baselines.ts) — same shape, different rows.
//
// Inputs:
//   - parsed predictions (grouped by submitter)
//   - truthByDate map (caller computes this from raw rows + filter)
//   - baseline key for the rWIS denominator
//
// Output: one SubmitterScore per submitter, with WIS, MAE, rWIS, and
// 95%-coverage if available. Submitters whose dates don't overlap the
// truth get scoredCount=0 and null scores — the UI surfaces them rather
// than dropping them.

import type { ParsedPredictions, PredictionRow } from "./companion";
import {
  alignedPairs,
  meanAbsoluteError,
  type JoinedPoint
} from "./metrics";
import {
  buildQuantileForecasts as _buildQuantileForecasts,
  type QuantileForecastPoint
} from "./quantile";
import {
  coverageRates,
  meanWIS,
  scoreForecasts,
  type CoverageStat
} from "./wis";
import {
  runBaseline,
  type BaselineKey,
  type TruthPoint
} from "./baselines";

// suppress unused-import warning for buildQuantileForecasts — kept around
// in case downstream code wants the existing helper.
void _buildQuantileForecasts;

export interface SubmitterScore {
  submitter: string;
  scoredCount: number;
  mae: number | null;
  wis: number | null;
  rWIS: number | null;
  coverage95: number | null;
  coverage80: number | null;
  isSynthetic: boolean;
  hasQuantiles: boolean;
}

/**
 * Build per-date QuantileForecastPoints from a submitter's prediction
 * rows. Multiple rows for the same (date, quantile) get averaged — the
 * common case for a single submitter is exactly one row, so this is a
 * no-op in practice.
 */
export function buildSubmitterForecasts(
  rows: PredictionRow[]
): Map<string, QuantileForecastPoint> {
  const acc = new Map<
    string,
    { pointSum: number; pointCount: number; quantileSums: Map<number, { sum: number; count: number }> }
  >();
  for (const r of rows) {
    let entry = acc.get(r.date);
    if (!entry) {
      entry = { pointSum: 0, pointCount: 0, quantileSums: new Map() };
      acc.set(r.date, entry);
    }
    if (r.quantile === null) {
      entry.pointSum += r.value;
      entry.pointCount += 1;
    } else {
      const qe = entry.quantileSums.get(r.quantile);
      if (qe) {
        qe.sum += r.value;
        qe.count += 1;
      } else {
        entry.quantileSums.set(r.quantile, { sum: r.value, count: 1 });
      }
    }
  }
  const out = new Map<string, QuantileForecastPoint>();
  for (const [date, e] of acc) {
    const quantiles = new Map<number, number>();
    for (const [q, { sum, count }] of e.quantileSums) {
      quantiles.set(q, sum / count);
    }
    let point: number | null = e.pointCount > 0 ? e.pointSum / e.pointCount : null;
    // Median fallback when no point row was provided.
    if (point === null && quantiles.has(0.5)) point = quantiles.get(0.5)!;
    out.set(date, { date, point, quantiles });
  }
  return out;
}

const PAIR_EPS = 1e-3;

function findCoverage(stats: CoverageStat[], width: number): number | null {
  const hit = stats.find((s) => Math.abs(s.intervalWidth - width) < PAIR_EPS);
  return hit ? hit.empiricalRate : null;
}

export function computeSubmitterScores(
  parsed: ParsedPredictions,
  truthByDate: Map<string, number>,
  baselineKey: BaselineKey = "naive-last-value"
): SubmitterScore[] {
  const truthPoints: TruthPoint[] = Array.from(truthByDate.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, value]) => ({ date, value }));

  const out: SubmitterScore[] = [];
  for (const summary of parsed.submitters) {
    const rows = parsed.rowsBySubmitter.get(summary.submitter) ?? [];
    const forecasts = buildSubmitterForecasts(rows);

    // Quantile-aware scoring (WIS + coverage)
    const scored = scoreForecasts(forecasts, truthByDate);
    const wisVal = meanWIS(scored);
    const cov = coverageRates(scored);
    const cov95 = findCoverage(cov, 0.95);
    const cov80 = findCoverage(cov, 0.80);
    const hasQuantiles = scored.some((s) => s.pairs.length > 0);

    // Point-pair MAE
    const allDates = new Set<string>([
      ...forecasts.keys(),
      ...truthByDate.keys()
    ]);
    const joined: JoinedPoint[] = Array.from(allDates)
      .sort()
      .map((date) => ({
        date,
        predicted: forecasts.get(date)?.point ?? null,
        observed: truthByDate.get(date) ?? null
      }));
    const aligned = alignedPairs(joined);
    const mae = meanAbsoluteError(aligned.predicted, aligned.observed);

    // rWIS vs baseline (deterministic forecast, so baseline WIS = MAE)
    const forecastDates = Array.from(forecasts.keys());
    const baselinePreds = runBaseline(baselineKey, truthPoints, forecastDates);
    const baselineForecasts = new Map<string, QuantileForecastPoint>();
    for (const [d, v] of baselinePreds) {
      baselineForecasts.set(d, { date: d, point: v, quantiles: new Map() });
    }
    const baselineScored = scoreForecasts(baselineForecasts, truthByDate);
    const baselineWIS = meanWIS(baselineScored);
    const rWIS =
      wisVal !== null && baselineWIS !== null && baselineWIS > 0
        ? wisVal / baselineWIS
        : null;

    out.push({
      submitter: summary.submitter,
      scoredCount: aligned.predicted.length,
      mae,
      wis: wisVal,
      rWIS,
      coverage95: cov95,
      coverage80: cov80,
      isSynthetic: summary.isSynthetic,
      hasQuantiles
    });
  }
  return out;
}

export interface TruthFilter {
  name: string;
  value: string;
}

export interface TruthAggOptions {
  /** Precise column-based filters — same shape the chart uses. Rows
   *  must equal the value on each named column. */
  filters?: TruthFilter[];
  /** "mean" or "sum" — default mean. */
  method?: "mean" | "sum";
}

/**
 * Aggregate truth rows into Map<date, number> for scoring. Filter rows
 * by precise column matches (truth.name === filter.value), then aggregate
 * by date with the given method.
 */
export function aggregateTruthForScoring(
  rows: Array<Record<string, unknown>>,
  dateField: string,
  valueField: string,
  opts: TruthAggOptions = {}
): Map<string, number> {
  const filters = opts.filters ?? [];
  const method = opts.method ?? "mean";

  const sums = new Map<string, { sum: number; count: number }>();
  for (const row of rows) {
    if (filters.length > 0) {
      let passes = true;
      for (const f of filters) {
        if (String(row[f.name] ?? "") !== f.value) {
          passes = false;
          break;
        }
      }
      if (!passes) continue;
    }
    const dateRaw = row[dateField];
    const dateStr = typeof dateRaw === "string" ? dateRaw : String(dateRaw ?? "");
    const date = dateStr.slice(0, 10);
    if (!date) continue;
    const valRaw = row[valueField];
    const val = typeof valRaw === "number" ? valRaw : Number(valRaw);
    if (!Number.isFinite(val)) continue;
    const curr = sums.get(date);
    if (curr) {
      curr.sum += val;
      curr.count += 1;
    } else {
      sums.set(date, { sum: val, count: 1 });
    }
  }
  const out = new Map<string, number>();
  for (const [d, { sum, count }] of sums) {
    out.set(d, method === "sum" ? sum : sum / count);
  }
  return out;
}

/**
 * Detect the most common dim value across all prediction rows, to scope
 * truth to the same subset by default. e.g. if every prediction row has
 * `location: "CA"`, returns ["CA"].
 *
 * Returns at most one value per dim column; the dim is included only if
 * a single value dominates (>50% of rows). Otherwise the dim is omitted
 * (caller falls back to no filter on that axis).
 */
export function dominantPredictionDimValues(parsed: ParsedPredictions): string[] {
  const out: string[] = [];
  for (const dim of parsed.dimNames) {
    const counts = new Map<string, number>();
    for (const r of parsed.rows) {
      const v = r.dims[dim];
      if (v === undefined) continue;
      counts.set(v, (counts.get(v) ?? 0) + 1);
    }
    if (counts.size === 0) continue;
    const total = parsed.rows.length;
    const [topVal, topCount] = Array.from(counts.entries()).sort(
      (a, b) => b[1] - a[1]
    )[0];
    if (topCount / total > 0.5) out.push(topVal);
  }
  return out;
}
