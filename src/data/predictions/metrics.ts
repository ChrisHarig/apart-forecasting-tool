import type { DatasetRow } from "../hf/rows";

export interface JoinedPoint {
  date: string;
  predicted: number | null;
  observed: number | null;
}

export interface PointSeries {
  rows: DatasetRow[];
  dateField: string;
  valueField: string;
}

export function outerJoinByDate(
  predictions: PointSeries,
  truth: PointSeries
): JoinedPoint[] {
  const predByDate = aggregateByDate(predictions);
  const truthByDate = aggregateByDate(truth);
  const allDates = new Set<string>([...predByDate.keys(), ...truthByDate.keys()]);
  return Array.from(allDates)
    .sort()
    .map((date) => ({
      date,
      predicted: predByDate.get(date) ?? null,
      observed: truthByDate.get(date) ?? null
    }));
}

function aggregateByDate(series: PointSeries): Map<string, number> {
  const sums = new Map<string, { sum: number; count: number }>();
  for (const row of series.rows) {
    const dateRaw = row[series.dateField];
    const dateStr = typeof dateRaw === "string" ? dateRaw : String(dateRaw ?? "");
    const date = dateStr.slice(0, 10);
    if (!date) continue;
    const valRaw = row[series.valueField];
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
  for (const [d, { sum, count }] of sums) out.set(d, sum / count);
  return out;
}

export interface ScoredPairs {
  predicted: number[];
  observed: number[];
}

export function alignedPairs(joined: JoinedPoint[]): ScoredPairs {
  const predicted: number[] = [];
  const observed: number[] = [];
  for (const p of joined) {
    if (p.predicted === null || p.observed === null) continue;
    predicted.push(p.predicted);
    observed.push(p.observed);
  }
  return { predicted, observed };
}

export function meanAbsoluteError(
  predicted: number[],
  observed: number[]
): number | null {
  const n = Math.min(predicted.length, observed.length);
  if (n === 0) return null;
  let sum = 0;
  for (let i = 0; i < n; i++) sum += Math.abs(predicted[i] - observed[i]);
  return sum / n;
}

export function rootMeanSquaredError(
  predicted: number[],
  observed: number[]
): number | null {
  const n = Math.min(predicted.length, observed.length);
  if (n === 0) return null;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const e = predicted[i] - observed[i];
    sum += e * e;
  }
  return Math.sqrt(sum / n);
}

// Mean absolute percentage error as a fraction (0.05 = 5%). Skips rows
// where the observed value is exactly 0 to avoid divide-by-zero; returns
// null if every observation is 0.
export function meanAbsolutePercentageError(
  predicted: number[],
  observed: number[]
): number | null {
  const n = Math.min(predicted.length, observed.length);
  if (n === 0) return null;
  let sum = 0;
  let count = 0;
  for (let i = 0; i < n; i++) {
    const o = observed[i];
    if (o === 0) continue;
    sum += Math.abs((predicted[i] - o) / o);
    count++;
  }
  if (count === 0) return null;
  return sum / count;
}

export function signedBias(
  predicted: number[],
  observed: number[]
): number | null {
  const n = Math.min(predicted.length, observed.length);
  if (n === 0) return null;
  let sum = 0;
  for (let i = 0; i < n; i++) sum += predicted[i] - observed[i];
  return sum / n;
}
