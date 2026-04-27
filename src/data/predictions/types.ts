import type { DatasetRow } from "../hf/rows";

// User-uploaded prediction or dataset, held in memory for the session.
// Slice 2 covers point + quantile predictions in long format:
// `(date, [quantile], target_column, value)` — one row per quantile, with
// `quantile=NULL` reserved for the point estimate (median fallback).
// Categorical-dim picks (when the CSV omits a dim the truth has) come in
// Slice 2C.
export interface UserDataset {
  id: string;
  filename: string;
  uploadedAt: number;
  rows: DatasetRow[];
  dateField: string;
  // Value columns excluding the quantile column. The first entry is the
  // default predicted value column for compare-to.
  numericFields: string[];
  // Detected quantile column (if any). Null = pure point CSV.
  quantileField: string | null;
  rowCount: number;
}
