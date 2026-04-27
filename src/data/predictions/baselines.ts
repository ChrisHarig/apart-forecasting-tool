// Baselines for rWIS denominators and dashboard comparison. All produce
// deterministic point predictions: Map<date, predictedValue>. WIS for a
// deterministic forecast reduces to MAE (no interval terms).
//
// Truth is passed in as { date, value } pairs; the caller is responsible
// for picking the truth dataset's date and value fields out of raw rows.

const MS_PER_DAY = 24 * 60 * 60 * 1000;

export interface TruthPoint {
  date: string; // YYYY-MM-DD
  value: number;
}

export type BaselineKey =
  | "naive-last-value"
  | "naive-last-week"
  | "seasonal-naive"
  | "linear-trend";

export const BASELINE_LABELS: Record<BaselineKey, string> = {
  "naive-last-value": "Naive (last value)",
  "naive-last-week": "Naive (last week)",
  "seasonal-naive": "Seasonal naive (1y ago)",
  "linear-trend": "Linear trend (last 8)"
};

// Predict each forecast date as the most recent truth strictly before it.
export function naiveLastValue(
  truth: TruthPoint[],
  forecastDates: string[]
): Map<string, number> {
  const sorted = [...truth].sort((a, b) => a.date.localeCompare(b.date));
  const out = new Map<string, number>();
  for (const target of forecastDates) {
    let lastValue: number | null = null;
    for (const t of sorted) {
      if (t.date < target) lastValue = t.value;
      else break;
    }
    if (lastValue !== null) out.set(target, lastValue);
  }
  return out;
}

// Predict target_date using truth at (target_date − 7 days), with a ±3-day
// fallback so off-by-one cadences (e.g. weekly Sat vs. weekly Sun) still
// land somewhere reasonable.
export function naiveLastWeek(
  truth: TruthPoint[],
  forecastDates: string[]
): Map<string, number> {
  const truthMap = new Map<string, number>();
  for (const t of truth) truthMap.set(t.date, t.value);
  const out = new Map<string, number>();
  for (const target of forecastDates) {
    const targetMs = Date.parse(target);
    if (!Number.isFinite(targetMs)) continue;
    const wantMs = targetMs - 7 * MS_PER_DAY;
    const exact = new Date(wantMs).toISOString().slice(0, 10);
    if (truthMap.has(exact)) {
      out.set(target, truthMap.get(exact)!);
      continue;
    }
    const v = nearestWithinTolerance(truthMap, wantMs, 3 * MS_PER_DAY);
    if (v !== null) out.set(target, v);
  }
  return out;
}

// Predict target_date using truth at (target_date − 365 days), week-of-year
// matched within ±7 days.
export function seasonalNaive(
  truth: TruthPoint[],
  forecastDates: string[]
): Map<string, number> {
  const truthMap = new Map<string, number>();
  for (const t of truth) truthMap.set(t.date, t.value);
  const out = new Map<string, number>();
  for (const target of forecastDates) {
    const targetMs = Date.parse(target);
    if (!Number.isFinite(targetMs)) continue;
    const wantMs = targetMs - 365 * MS_PER_DAY;
    const v = nearestWithinTolerance(truthMap, wantMs, 7 * MS_PER_DAY);
    if (v !== null) out.set(target, v);
  }
  return out;
}

// Linear-fit the last `windowSize` truth points (in day-numeric x), then
// extrapolate to each target date. Skips targets where there are fewer
// than 2 truth points to fit.
export function linearTrend(
  truth: TruthPoint[],
  forecastDates: string[],
  windowSize = 8
): Map<string, number> {
  const sorted = [...truth].sort((a, b) => a.date.localeCompare(b.date));
  const out = new Map<string, number>();
  for (const target of forecastDates) {
    const targetMs = Date.parse(target);
    if (!Number.isFinite(targetMs)) continue;
    const window = sorted.filter((t) => t.date < target).slice(-windowSize);
    if (window.length < 2) continue;
    const xs = window.map((t) => Math.floor(Date.parse(t.date) / MS_PER_DAY));
    const ys = window.map((t) => t.value);
    const fit = leastSquares(xs, ys);
    const xTarget = Math.floor(targetMs / MS_PER_DAY);
    out.set(target, fit.intercept + fit.slope * xTarget);
  }
  return out;
}

export function runBaseline(
  key: BaselineKey,
  truth: TruthPoint[],
  forecastDates: string[]
): Map<string, number> {
  switch (key) {
    case "naive-last-value":
      return naiveLastValue(truth, forecastDates);
    case "naive-last-week":
      return naiveLastWeek(truth, forecastDates);
    case "seasonal-naive":
      return seasonalNaive(truth, forecastDates);
    case "linear-trend":
      return linearTrend(truth, forecastDates);
  }
}

function nearestWithinTolerance(
  truthMap: Map<string, number>,
  targetMs: number,
  toleranceMs: number
): number | null {
  let bestVal: number | null = null;
  let bestDist = Infinity;
  for (const [d, v] of truthMap) {
    const dist = Math.abs(Date.parse(d) - targetMs);
    if (dist < bestDist && dist <= toleranceMs) {
      bestVal = v;
      bestDist = dist;
    }
  }
  return bestVal;
}

function leastSquares(xs: number[], ys: number[]): { slope: number; intercept: number } {
  const n = xs.length;
  let sumX = 0;
  let sumY = 0;
  for (let i = 0; i < n; i++) {
    sumX += xs[i];
    sumY += ys[i];
  }
  const meanX = sumX / n;
  const meanY = sumY / n;
  let num = 0;
  let den = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - meanX;
    num += dx * (ys[i] - meanY);
    den += dx * dx;
  }
  const slope = den === 0 ? 0 : num / den;
  return { slope, intercept: meanY - slope * meanX };
}
