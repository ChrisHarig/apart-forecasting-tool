import { fetchRows } from "./client";
import { readCache, writeCache } from "./cache";

export type DatasetRow = Record<string, unknown>;

export interface DatasetSlice {
  datasetId: string;
  rows: DatasetRow[];
  numRowsTotal: number;
  truncated: boolean;
}

export interface RecentRowsResult {
  datasetId: string;
  rows: DatasetRow[];
  dateField: string | null;
  latestDate: string | null;
  numRowsTotal: number;
}

const PAGE_SIZE = 100;
// Bumped from 5,000 → 10,000 so medium-sized datasets (delphi-flusurv at 9.3k,
// canada-fluwatch at 2.7k, ukhsa-respiratory at 1.3k) come down complete.
// Larger datasets (nyt-covid 2.5M, jhu-csse-covid 225k, …) still get truncated
// to the first 10k rows in chronological order — known-biased toward early
// data, follow-up TODO is stratified sampling. The truncation indicator in
// the UI tells the user when this is happening.
const MAX_ROWS = 10_000;
const LATEST_TAIL = 100;
const DEFAULT_RECENT_N = 4;

function rowsKey(datasetId: string, max: number) {
  return `rows:${datasetId}:${max}`;
}

function recentKey(datasetId: string, n: number) {
  return `recent:${datasetId}:${n}`;
}

export async function getDatasetSlice(
  datasetId: string,
  opts: { max?: number; force?: boolean } = {}
): Promise<DatasetSlice> {
  const max = Math.min(opts.max ?? MAX_ROWS, MAX_ROWS);
  if (!opts.force) {
    const cached = readCache<DatasetSlice>(rowsKey(datasetId, max));
    if (cached) return cached;
  }

  const collected: DatasetRow[] = [];
  let offset = 0;
  let total = 0;
  while (collected.length < max) {
    const length = Math.min(PAGE_SIZE, max - collected.length);
    const page = await fetchRows(datasetId, { offset, length });
    total = page.num_rows_total ?? collected.length + page.rows.length;
    for (const r of page.rows) collected.push(r.row);
    if (page.rows.length < length) break;
    offset += page.rows.length;
    if (offset >= total) break;
  }

  const slice: DatasetSlice = {
    datasetId,
    rows: collected,
    numRowsTotal: total,
    truncated: total > collected.length
  };
  writeCache(rowsKey(datasetId, max), slice);
  return slice;
}

export async function getRecentRows(
  datasetId: string,
  opts: { n?: number; knownTotal?: number; force?: boolean } = {}
): Promise<RecentRowsResult> {
  const n = opts.n ?? DEFAULT_RECENT_N;

  if (!opts.force) {
    const cached = readCache<RecentRowsResult>(recentKey(datasetId, n));
    if (cached) return cached;
  }

  // First page tells us total + sample.
  const head = await fetchRows(datasetId, { offset: 0, length: Math.min(LATEST_TAIL, PAGE_SIZE) });
  const total = head.num_rows_total ?? opts.knownTotal ?? head.rows.length;

  let candidates = head.rows.map((r) => r.row);

  // If there are more rows, grab the tail too — EPI-Eval data is typically
  // chronological, so the tail is most likely to contain the latest dates.
  if (total > candidates.length) {
    const tailOffset = Math.max(0, total - LATEST_TAIL);
    const tail = await fetchRows(datasetId, { offset: tailOffset, length: Math.min(LATEST_TAIL, total - tailOffset) });
    candidates = tail.rows.map((r) => r.row);
  }

  const dateField = detectDateField(candidates);
  let recent: DatasetRow[];

  if (dateField) {
    recent = candidates
      .filter((r) => r[dateField] !== null && r[dateField] !== undefined && r[dateField] !== "")
      .sort((a, b) => String(b[dateField]).localeCompare(String(a[dateField])))
      .slice(0, n);
  } else {
    // No date — fall back to "last N as returned" (likely insertion order).
    recent = candidates.slice(-n).reverse();
  }

  const latestDate = dateField && recent[0] ? String(recent[0][dateField]).slice(0, 10) : null;

  const result: RecentRowsResult = { datasetId, rows: recent, dateField, latestDate, numRowsTotal: total };
  writeCache(recentKey(datasetId, n), result);
  return result;
}

export function detectCategoricalFields(
  rows: DatasetRow[],
  skip: string[] = [],
  opts: { maxCardinality?: number; sampleSize?: number } = {}
): { name: string; values: string[] }[] {
  if (rows.length === 0) return [];
  const maxCardinality = opts.maxCardinality ?? 50;
  const sampleSize = Math.min(rows.length, opts.sampleSize ?? 500);
  const skipSet = new Set(skip);
  const out: { name: string; values: string[] }[] = [];

  const keys = new Set<string>();
  for (let i = 0; i < Math.min(rows.length, 50); i++) for (const k of Object.keys(rows[i])) keys.add(k);

  for (const key of keys) {
    if (skipSet.has(key)) continue;
    const seen = new Set<string>();
    let nonNull = 0;
    let bailed = false;
    for (let i = 0; i < sampleSize; i++) {
      const v = rows[i]?.[key];
      if (v === null || v === undefined || v === "") continue;
      nonNull++;
      seen.add(String(v));
      if (seen.size > maxCardinality) {
        bailed = true;
        break;
      }
    }
    if (bailed || nonNull === 0 || seen.size < 2) continue;
    out.push({ name: key, values: Array.from(seen).sort() });
  }
  return out;
}

export function detectDateField(rows: DatasetRow[]): string | null {
  if (rows.length === 0) return null;
  const candidates = ["date", "observed_at", "observed_date", "week_ending", "report_date"];
  const keys = Object.keys(rows[0]);
  for (const c of candidates) if (keys.includes(c)) return c;
  return keys.find((k) => k.toLowerCase().includes("date")) ?? null;
}

export function detectNumericFields(rows: DatasetRow[], skip: string[] = []): string[] {
  if (rows.length === 0) return [];
  const skipSet = new Set(skip);
  const out: string[] = [];
  for (const key of Object.keys(rows[0])) {
    if (skipSet.has(key)) continue;
    let numericHits = 0;
    let nonNullSamples = 0;
    for (let i = 0; i < Math.min(rows.length, 50); i++) {
      const v = rows[i][key];
      if (v === null || v === undefined || v === "") continue;
      nonNullSamples++;
      if (typeof v === "number" || (typeof v === "string" && !Number.isNaN(Number(v)))) numericHits++;
    }
    if (nonNullSamples > 0 && numericHits / nonNullSamples > 0.8) out.push(key);
  }
  return out;
}
