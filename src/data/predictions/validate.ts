import type { SourceMetadata } from "../../types/source";
import type { UserDataset } from "./types";

// Forecast horizon: predictions whose target_date is more than this many
// days past the truth's coverage end are out-of-range. Matches the v2 doc
// rule ("anywhere between truth.start and ~2 months past time_coverage.end").
const FORECAST_HORIZON_DAYS = 60;
const MS_PER_DAY = 24 * 60 * 60 * 1000;

export interface DateValidation {
  ok: boolean;
  outOfRangeRows: number[];
  parseErrorRows: number[];
  acceptedRange: { min: string; max: string } | null;
}

export function validateDates(
  prediction: UserDataset,
  target: SourceMetadata
): DateValidation {
  const range = deriveAcceptableRange(target);
  if (!range) {
    return { ok: true, outOfRangeRows: [], parseErrorRows: [], acceptedRange: null };
  }
  const minMs = Date.parse(range.min);
  const maxMs = Date.parse(range.max);
  if (!Number.isFinite(minMs) || !Number.isFinite(maxMs)) {
    return { ok: true, outOfRangeRows: [], parseErrorRows: [], acceptedRange: null };
  }
  const outOfRangeRows: number[] = [];
  const parseErrorRows: number[] = [];
  for (let i = 0; i < prediction.rows.length; i++) {
    const dateRaw = prediction.rows[i][prediction.dateField];
    const dateStr = typeof dateRaw === "string" ? dateRaw : String(dateRaw ?? "");
    const ms = Date.parse(dateStr.slice(0, 10));
    if (!Number.isFinite(ms)) {
      parseErrorRows.push(i);
      continue;
    }
    if (ms < minMs || ms > maxMs) outOfRangeRows.push(i);
  }
  return {
    ok: outOfRangeRows.length === 0 && parseErrorRows.length === 0,
    outOfRangeRows,
    parseErrorRows,
    acceptedRange: range
  };
}

export function deriveAcceptableRange(
  target: SourceMetadata
): { min: string; max: string } | null {
  const coverage = target.computed?.time_coverage;
  if (!coverage || coverage.length === 0) return null;
  const min = coverage[0]?.start;
  const lastEnd = coverage[coverage.length - 1]?.end;
  if (!min || !lastEnd) return null;
  const endStr =
    lastEnd === "present" ? new Date().toISOString().slice(0, 10) : lastEnd;
  const endMs = Date.parse(endStr);
  if (!Number.isFinite(endMs)) return null;
  const horizonMs = endMs + FORECAST_HORIZON_DAYS * MS_PER_DAY;
  const max = new Date(horizonMs).toISOString().slice(0, 10);
  return { min, max };
}
