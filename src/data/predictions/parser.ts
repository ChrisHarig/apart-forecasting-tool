import Papa from "papaparse";
import type { DatasetRow } from "../hf/rows";
import { detectDateField, detectNumericFields } from "../hf/rows";
import type { UserDataset } from "./types";

const DATE_HEADER_HINTS = [
  "date",
  "target_date",
  "forecast_date",
  "week_ending",
  "report_date",
  "as_of"
];

const QUANTILE_HEADER_HINTS = ["quantile"];

export interface ParsedCsv {
  rows: DatasetRow[];
  fields: string[];
  parseErrors: string[];
}

export function parseCsvText(text: string): ParsedCsv {
  const cleaned = text.replace(/^﻿/, "");
  const result = Papa.parse<Record<string, string>>(cleaned, {
    header: true,
    skipEmptyLines: true,
    dynamicTyping: false,
    transformHeader: (h) => h.trim()
  });
  const fields = (result.meta.fields ?? []).map((f) => f.trim());
  const rows: DatasetRow[] = result.data.map((raw) => coerceRow(raw, fields));
  const parseErrors = (result.errors ?? []).map(
    (e) => `Row ${e.row ?? "?"}: ${e.message}`
  );
  return { rows, fields, parseErrors };
}

function coerceRow(raw: Record<string, string>, fields: string[]): DatasetRow {
  const out: DatasetRow = {};
  for (const f of fields) {
    const v = raw[f];
    if (v === undefined || v === null || v === "") {
      out[f] = null;
      continue;
    }
    const trimmed = typeof v === "string" ? v.trim() : v;
    if (typeof trimmed === "string" && trimmed !== "" && isNumericLiteral(trimmed)) {
      out[f] = Number(trimmed);
    } else {
      out[f] = trimmed;
    }
  }
  return out;
}

function isNumericLiteral(s: string): boolean {
  if (s.length === 0) return false;
  if (!/^-?\d/.test(s) && !/^-?\./.test(s)) return false;
  return Number.isFinite(Number(s));
}

export interface BuildOptions {
  filename: string;
}

export type BuildResult =
  | { ok: true; dataset: UserDataset }
  | { ok: false; errors: string[] };

export function buildUserDataset(parsed: ParsedCsv, opts: BuildOptions): BuildResult {
  const errors: string[] = [];
  if (parsed.rows.length === 0) {
    errors.push("CSV had no data rows.");
  }
  const dateField = pickDateField(parsed.rows, parsed.fields);
  if (!dateField) {
    errors.push(
      "No date column found. Add a column named `date`, `target_date`, or similar."
    );
  }
  const quantileField = pickQuantileField(parsed.fields);
  if (quantileField) {
    validateQuantileValues(parsed.rows, quantileField, errors);
  }

  const skipForNumeric = [dateField, quantileField].filter(
    (f): f is string => typeof f === "string" && f.length > 0
  );
  const numericFields = detectNumericFields(parsed.rows, skipForNumeric);
  if (numericFields.length === 0) {
    errors.push(
      "No numeric value column found. Add at least one column with numeric values (e.g. `value`, `prediction`)."
    );
  }
  if (errors.length > 0) return { ok: false, errors };
  return {
    ok: true,
    dataset: {
      id: generateUserDatasetId(),
      filename: opts.filename,
      uploadedAt: Date.now(),
      rows: parsed.rows,
      dateField: dateField!,
      numericFields,
      quantileField,
      rowCount: parsed.rows.length
    }
  };
}

function pickDateField(rows: DatasetRow[], fields: string[]): string | null {
  for (const hint of DATE_HEADER_HINTS) {
    if (fields.includes(hint)) return hint;
  }
  return detectDateField(rows);
}

function pickQuantileField(fields: string[]): string | null {
  for (const hint of QUANTILE_HEADER_HINTS) {
    if (fields.includes(hint)) return hint;
  }
  // Case-insensitive fallback: tolerate "Quantile" / "QUANTILE".
  const lower = fields.map((f) => f.toLowerCase());
  for (const hint of QUANTILE_HEADER_HINTS) {
    const idx = lower.indexOf(hint);
    if (idx >= 0) return fields[idx];
  }
  return null;
}

function validateQuantileValues(
  rows: DatasetRow[],
  quantileField: string,
  errors: string[]
): void {
  let bad = 0;
  let firstBadRow = -1;
  for (let i = 0; i < rows.length; i++) {
    const v = rows[i][quantileField];
    if (v === null || v === undefined) continue;
    if (typeof v !== "number" || !Number.isFinite(v) || v < 0 || v > 1) {
      bad++;
      if (firstBadRow < 0) firstBadRow = i;
    }
  }
  if (bad > 0) {
    errors.push(
      `Quantile column has ${bad} row${bad === 1 ? "" : "s"} with values outside [0, 1] or non-numeric (first at row ${
        firstBadRow + 1
      }).`
    );
  }
}

function generateUserDatasetId(): string {
  return `user-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
