import type { DatasetRow } from "../hf/rows";

// Per-date quantile forecast: a point estimate (typically the median) and
// a sparse map of quantile → value. Built from raw long-format rows where
// a row with quantile=null marks the point estimate; rows with quantile in
// (0, 1) carry interval bounds.
export interface QuantileForecastPoint {
  date: string;
  point: number | null;
  quantiles: Map<number, number>;
}

export function buildQuantileForecasts(
  rows: DatasetRow[],
  dateField: string,
  valueField: string,
  quantileField: string | null
): Map<string, QuantileForecastPoint> {
  const out = new Map<string, QuantileForecastPoint>();
  // Point rows (quantile null/missing) get averaged within a date to mirror
  // the join-side aggregation in metrics.outerJoinByDate.
  const pointSums = new Map<string, { sum: number; count: number }>();

  for (const row of rows) {
    const dateRaw = row[dateField];
    const date =
      typeof dateRaw === "string"
        ? dateRaw.slice(0, 10)
        : String(dateRaw ?? "").slice(0, 10);
    if (!date) continue;

    const valRaw = row[valueField];
    const val = typeof valRaw === "number" ? valRaw : Number(valRaw);
    if (!Number.isFinite(val)) continue;

    let entry = out.get(date);
    if (!entry) {
      entry = { date, point: null, quantiles: new Map() };
      out.set(date, entry);
    }

    const qRaw = quantileField ? row[quantileField] : null;
    if (qRaw === null || qRaw === undefined || qRaw === "") {
      const ps = pointSums.get(date) ?? { sum: 0, count: 0 };
      ps.sum += val;
      ps.count += 1;
      pointSums.set(date, ps);
    } else {
      const q = typeof qRaw === "number" ? qRaw : Number(qRaw);
      if (!Number.isFinite(q) || q < 0 || q > 1) continue;
      entry.quantiles.set(q, val);
    }
  }

  for (const [date, { sum, count }] of pointSums) {
    const entry = out.get(date);
    if (entry) entry.point = sum / count;
  }

  // Median fallback: quantile-only CSVs (no quantile=null rows) still get
  // a usable point estimate.
  for (const entry of out.values()) {
    if (entry.point === null && entry.quantiles.has(0.5)) {
      entry.point = entry.quantiles.get(0.5)!;
    }
  }

  return out;
}

// A symmetric quantile pair forms a central prediction interval.
// alpha = 2 * lowerQuantile (Bracher 2021 convention): coverage = 1 - alpha.
// e.g. q=0.25 ↔ q=0.75 → alpha=0.5, 50% interval.
export interface IntervalPair {
  alpha: number;
  intervalWidth: number;
  lowerQuantile: number;
  upperQuantile: number;
  lowerValue: number;
  upperValue: number;
}

const PAIR_EPS = 1e-6;

export function findIntervalPairs(quantiles: Map<number, number>): IntervalPair[] {
  const out: IntervalPair[] = [];
  const sortedKeys = Array.from(quantiles.keys()).sort((a, b) => a - b);
  for (const q of sortedKeys) {
    if (q >= 0.5 - PAIR_EPS) break;
    const upperQ = 1 - q;
    let upperVal: number | undefined;
    let upperKey = upperQ;
    for (const u of quantiles.keys()) {
      if (Math.abs(u - upperQ) < PAIR_EPS) {
        upperVal = quantiles.get(u);
        upperKey = u;
        break;
      }
    }
    if (upperVal === undefined) continue;
    const lowerVal = quantiles.get(q)!;
    const alpha = 2 * q;
    out.push({
      alpha,
      intervalWidth: 1 - alpha,
      lowerQuantile: q,
      upperQuantile: upperKey,
      lowerValue: lowerVal,
      upperValue: upperVal
    });
  }
  return out;
}
