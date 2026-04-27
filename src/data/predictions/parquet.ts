// Serialize a user-uploaded prediction dataset into the long-format
// parquet that EPI-Eval/{target}-predictions sibling datasets expect.
//
// Schema (one row per quantile per date per category combination):
//   target_date    STRING (YYYY-MM-DD)
//   target_dataset STRING — e.g. "nhsn-hrd"
//   target_column  STRING — the truth column the prediction targets
//   submitter      STRING
//   model_name     STRING
//   description    STRING
//   quantile       DOUBLE nullable (null = point estimate)
//   value          DOUBLE
//   submitted_at   STRING (ISO 8601 UTC)
//   {…dim columns} STRING — any categorical dims from the source CSV
//
// Repeated metadata columns dictionary-encode efficiently; not worth
// normalizing further at this scale.

import { parquetWriteBuffer } from "hyparquet-writer";
import type { UserDataset } from "./types";

export const PREDICTIONS_SCHEMA_VERSION = 1;

export interface SubmissionMetadata {
  submitter: string;
  modelName: string;
  description: string;
  targetDataset: string;
  targetColumn: string;
  /** Categorical dimension columns to include from the user CSV. */
  passthroughDims?: string[];
  /** Override submission timestamp; defaults to now. */
  submittedAt?: Date;
}

export interface SerializedSubmission {
  buffer: ArrayBuffer;
  rowCount: number;
  filename: string;
}

export function serializePredictionParquet(
  dataset: UserDataset,
  meta: SubmissionMetadata
): SerializedSubmission {
  const valueField = dataset.numericFields[0];
  if (!valueField) {
    throw new Error("Prediction dataset has no value column");
  }

  const dims = meta.passthroughDims ?? [];
  const submittedAt = (meta.submittedAt ?? new Date()).toISOString();

  const targetDate: (string | null)[] = [];
  const value: (number | null)[] = [];
  const quantile: (number | null)[] = [];
  const dimCols: Record<string, (string | null)[]> = Object.fromEntries(
    dims.map((d) => [d, [] as (string | null)[]])
  );

  for (const row of dataset.rows) {
    const dateRaw = row[dataset.dateField];
    const date = normalizeDate(dateRaw);
    if (!date) continue;

    const valRaw = row[valueField];
    const val = toNumber(valRaw);
    if (val === null) continue;

    let q: number | null = null;
    if (dataset.quantileField) {
      const qRaw = row[dataset.quantileField];
      if (qRaw !== null && qRaw !== undefined && qRaw !== "") {
        const qNum = toNumber(qRaw);
        if (qNum !== null && qNum >= 0 && qNum <= 1) q = qNum;
      }
    }

    targetDate.push(date);
    value.push(val);
    quantile.push(q);
    for (const d of dims) {
      const v = row[d];
      dimCols[d].push(v === null || v === undefined ? null : String(v));
    }
  }

  const rowCount = targetDate.length;
  if (rowCount === 0) {
    throw new Error("No valid prediction rows to serialize");
  }

  const repeated = (s: string) => Array.from({ length: rowCount }, () => s);

  const columnData = [
    { name: "target_date", data: targetDate, type: "STRING" as const, nullable: false },
    {
      name: "target_dataset",
      data: repeated(meta.targetDataset),
      type: "STRING" as const,
      nullable: false
    },
    {
      name: "target_column",
      data: repeated(meta.targetColumn),
      type: "STRING" as const,
      nullable: false
    },
    {
      name: "submitter",
      data: repeated(meta.submitter),
      type: "STRING" as const,
      nullable: false
    },
    {
      name: "model_name",
      data: repeated(meta.modelName),
      type: "STRING" as const,
      nullable: false
    },
    {
      name: "description",
      data: repeated(meta.description),
      type: "STRING" as const,
      nullable: false
    },
    { name: "quantile", data: quantile, type: "DOUBLE" as const, nullable: true },
    { name: "value", data: value, type: "DOUBLE" as const, nullable: false },
    {
      name: "submitted_at",
      data: repeated(submittedAt),
      type: "STRING" as const,
      nullable: false
    },
    ...dims.map((d) => ({
      name: d,
      data: dimCols[d],
      type: "STRING" as const,
      nullable: true
    }))
  ];

  const buffer = parquetWriteBuffer({
    columnData,
    kvMetadata: [
      { key: "epi-eval.schema_version", value: String(PREDICTIONS_SCHEMA_VERSION) },
      { key: "epi-eval.target_dataset", value: meta.targetDataset },
      { key: "epi-eval.target_column", value: meta.targetColumn },
      { key: "epi-eval.submitter", value: meta.submitter },
      { key: "epi-eval.model_name", value: meta.modelName }
    ]
  });

  const stamp = submittedAt.replace(/[-:T.]/g, "").slice(0, 14);
  const safeName = sanitize(meta.submitter) || "anon";
  const safeModel = sanitize(meta.modelName);
  const filename = `data/${safeName}${safeModel ? `-${safeModel}` : ""}-${stamp}.parquet`;

  return { buffer, rowCount, filename };
}

function normalizeDate(v: unknown): string | null {
  if (typeof v !== "string" && typeof v !== "number") return null;
  const s = String(v).trim();
  if (!s) return null;
  const m = s.match(/^(\d{4}-\d{2}-\d{2})/);
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

function sanitize(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}
