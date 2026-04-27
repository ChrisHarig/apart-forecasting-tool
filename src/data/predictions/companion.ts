// Read-side support for the EPI-Eval/<id>-predictions companion repos.
// The submission write-path lives in hf-submit.ts; this module is the
// inverse — given a target dataset id, find its companion, fetch the rows
// the datasets-server has indexed, and parse them into per-submitter
// groups for the chart overlay.
//
// Schema we expect (matches `parquet.ts` and `seed_synth_predictions.py`):
//   target_date string · target_dataset · target_column · submitter ·
//   model_name · description · quantile (nullable double) · value · …dims
//
// Synthetic submissions can be flagged so the UI can distinguish them
// from real forecaster output. We rely on a simple naming heuristic
// (`team-*-synth-…` files, submitters prefixed `team-` from the seeder)
// since the per-file `epi-eval.synthetic` kv-metadata is not surfaced by
// the rows endpoint. Heuristic is deliberately loose; real submitters can
// override by avoiding the `team-` prefix.

import type { DatasetRow } from "../hf/rows";

export const PREDICTIONS_ORG = "EPI-Eval";

export function companionRepoId(targetDatasetId: string): string {
  return `${PREDICTIONS_ORG}/${targetDatasetId}-predictions`;
}

export interface PredictionRow {
  date: string;
  submitter: string;
  modelName: string;
  quantile: number | null; // null = point estimate
  value: number;
  // Pass-through dim columns (location, condition, etc.) preserved as-is
  // so the consumer can filter on them. Stored as a record for flexibility.
  dims: Record<string, string>;
}

export interface SubmitterSummary {
  submitter: string;
  modelNames: string[];
  rowCount: number;
  pointDateCount: number; // forecast horizon size
  isSynthetic: boolean;
}

export interface ParsedPredictions {
  rows: PredictionRow[];
  rowsBySubmitter: Map<string, PredictionRow[]>;
  submitters: SubmitterSummary[];
  /** All forecast dates across all submitters, sorted ascending. */
  allDates: string[];
  /** Date range observed; null if no rows. */
  dateRange: { min: string; max: string } | null;
  /** Pass-through dim column names observed across the rows. */
  dimNames: string[];
  /**
   * Target truth column the predictions forecast. Every row in a
   * companion repo carries `target_column`; we expose the most common
   * value here. Distinct values from heterogeneous submissions are
   * reported in `targetColumnsAll`.
   */
  targetColumn: string | null;
  targetColumnsAll: string[];
}

const KNOWN_NON_DIM_COLUMNS = new Set([
  "target_date",
  "target_dataset",
  "target_column",
  "submitter",
  "model_name",
  "description",
  "quantile",
  "value",
  "submitted_at"
]);

function normalizeDate(v: unknown): string | null {
  if (v === null || v === undefined) return null;
  const s = typeof v === "string" ? v : String(v);
  const trimmed = s.trim();
  if (!trimmed) return null;
  const m = trimmed.match(/^(\d{4}-\d{2}-\d{2})/);
  return m ? m[1] : null;
}

function toNumber(v: unknown): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function isLikelySynthetic(submitter: string): boolean {
  // Loose heuristic — our seeder uses `team-*` personas. Real users can
  // claim those names too; the badge is informational, not authoritative.
  return submitter.startsWith("team-");
}

export function parsePredictionRows(rawRows: DatasetRow[]): ParsedPredictions {
  const out: PredictionRow[] = [];
  const dimNames = new Set<string>();
  const allDates = new Set<string>();
  const targetColumnCounts = new Map<string, number>();

  for (const row of rawRows) {
    const date = normalizeDate(row.target_date);
    const submitter = typeof row.submitter === "string" ? row.submitter : null;
    const modelName = typeof row.model_name === "string" ? row.model_name : "";
    const value = toNumber(row.value);
    if (!date || !submitter || value === null) continue;
    if (typeof row.target_column === "string" && row.target_column.length > 0) {
      targetColumnCounts.set(
        row.target_column,
        (targetColumnCounts.get(row.target_column) ?? 0) + 1
      );
    }

    let q: number | null = null;
    if (row.quantile !== null && row.quantile !== undefined && row.quantile !== "") {
      const qNum = toNumber(row.quantile);
      if (qNum !== null && qNum >= 0 && qNum <= 1) q = qNum;
    }

    const dims: Record<string, string> = {};
    for (const k of Object.keys(row)) {
      if (KNOWN_NON_DIM_COLUMNS.has(k)) continue;
      const v = row[k];
      if (v === null || v === undefined || v === "") continue;
      dims[k] = String(v);
      dimNames.add(k);
    }

    out.push({
      date,
      submitter,
      modelName,
      quantile: q,
      value,
      dims
    });
    allDates.add(date);
  }

  const rowsBySubmitter = new Map<string, PredictionRow[]>();
  for (const r of out) {
    const list = rowsBySubmitter.get(r.submitter);
    if (list) list.push(r);
    else rowsBySubmitter.set(r.submitter, [r]);
  }

  const submitters: SubmitterSummary[] = Array.from(rowsBySubmitter.entries())
    .map(([submitter, rows]) => {
      const modelNames = Array.from(new Set(rows.map((r) => r.modelName))).sort();
      const pointDates = new Set(rows.filter((r) => r.quantile === null).map((r) => r.date));
      return {
        submitter,
        modelNames,
        rowCount: rows.length,
        pointDateCount: pointDates.size,
        isSynthetic: isLikelySynthetic(submitter)
      };
    })
    .sort((a, b) => a.submitter.localeCompare(b.submitter));

  const sortedDates = Array.from(allDates).sort();
  const targetColumnsAll = Array.from(targetColumnCounts.keys()).sort();
  const dominantTargetColumn =
    targetColumnsAll.length === 0
      ? null
      : Array.from(targetColumnCounts.entries()).sort((a, b) => b[1] - a[1])[0][0];
  return {
    rows: out,
    rowsBySubmitter,
    submitters,
    allDates: sortedDates,
    dateRange:
      sortedDates.length > 0
        ? { min: sortedDates[0], max: sortedDates[sortedDates.length - 1] }
        : null,
    dimNames: Array.from(dimNames).sort(),
    targetColumn: dominantTargetColumn,
    targetColumnsAll
  };
}
