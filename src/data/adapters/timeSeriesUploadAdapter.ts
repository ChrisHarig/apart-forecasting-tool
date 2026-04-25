import type {
  AggregateTimeSeriesDataset,
  AggregateTimeSeriesDatasetMetadata,
  AggregateTimeSeriesMetricSummary,
  AggregateTimeSeriesNormalizationResult,
  AggregateTimeSeriesPersistenceResult,
  AggregateTimeSeriesRecord,
  AggregateTimeSeriesUploadInput,
  AggregateTimeSeriesValidationIssue,
  AggregateTimeSeriesValueQuality,
  TimeSeriesRecord,
  TimeSeriesUploadFormat,
  TimeSeriesValidationResult,
  UploadedDataset
} from "../../types/timeseries";
import { normalizeIso3 } from "../../utils/countryCodes";
import {
  getAggregateRecordDateRange,
  normalizeDateInput,
  sortAggregateRecordsByDate
} from "../../utils/dateRange";
import { readJsonFromLocalStorage, writeJsonToLocalStorage } from "../../utils/localStorage";

export const DEFAULT_TIME_SERIES_STORAGE_KEY = "sentinel-atlas:uploaded-time-series";

const LEGACY_DATASETS_KEY = "sentinel-atlas:uploaded-datasets";
const LEGACY_REQUIRED_FIELDS = ["date", "metric", "value"];

type SourceRow = {
  rowNumber: number;
  fields: Record<string, unknown>;
};

type ParsedUpload = {
  rows: SourceRow[];
  format: TimeSeriesUploadFormat;
  sourceLabel?: string;
  datasetName?: string;
  issues: AggregateTimeSeriesValidationIssue[];
};

type FieldRead = {
  field: string;
  value: unknown;
};

const DATE_FIELD_ALIASES = [
  "date",
  "report_date",
  "reported_date",
  "observation_date",
  "observed_date",
  "timestamp",
  "time",
  "week_start",
  "period_start"
];

const VALUE_FIELD_ALIASES = [
  "value",
  "count",
  "cases",
  "case_count",
  "observations",
  "observed",
  "estimate",
  "signal",
  "signal_value",
  "index",
  "rate",
  "percentage",
  "percent"
];

const METRIC_FIELD_ALIASES = ["metric", "measure", "indicator", "variable", "series", "signal_name"];
const UNIT_FIELD_ALIASES = ["unit", "units", "value_unit"];
const GEOGRAPHY_ID_FIELD_ALIASES = ["geography_id", "geographyid", "geo_id", "location_id", "country_id", "iso3", "iso_numeric"];
const GEOGRAPHY_NAME_FIELD_ALIASES = ["geography", "geography_name", "location", "location_name", "country", "country_name", "region", "area"];
const PATHOGEN_ID_FIELD_ALIASES = ["pathogen_id", "pathogenid", "signal_id"];
const PATHOGEN_NAME_FIELD_ALIASES = ["pathogen", "pathogen_name", "signal_label"];
const SOURCE_FIELD_ALIASES = ["source", "source_name", "source_label", "dataset_source"];
const LOWER_FIELD_ALIASES = ["lower", "lower_bound", "low", "ci_lower", "confidence_lower"];
const UPPER_FIELD_ALIASES = ["upper", "upper_bound", "high", "ci_upper", "confidence_upper"];
const QUALITY_FIELD_ALIASES = ["quality", "status", "value_quality"];

const PRIVACY_RISK_FIELDS = new Set([
  "patient_id",
  "patient_name",
  "person_id",
  "person_name",
  "individual_id",
  "subject_id",
  "user_id",
  "device_id",
  "advertising_id",
  "email",
  "email_address",
  "phone",
  "phone_number",
  "medical_record_number",
  "mrn",
  "address",
  "home_address",
  "street_address",
  "first_name",
  "last_name",
  "full_name",
  "ip_address",
  "imei",
  "imsi",
  "ssn",
  "date_of_birth",
  "dob",
  "license_plate",
  "precise_gps",
  "gps_trace",
  "raw_trace",
  "trajectory",
  "contact_trace",
  "home_latitude",
  "home_longitude"
]);

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeFieldName(field: string): string {
  return field
    .replace(/^\uFEFF/, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function normalizeString(value: unknown): string | undefined {
  if (value === null || value === undefined) {
    return undefined;
  }

  const normalized = String(value).trim();
  return normalized.length > 0 ? normalized : undefined;
}

function normalizeQuality(value: unknown): AggregateTimeSeriesValueQuality | undefined {
  const normalized = normalizeString(value)?.toLowerCase();
  if (!normalized) {
    return undefined;
  }

  if (normalized === "reported" || normalized === "observed") {
    return "reported";
  }

  if (normalized === "estimated" || normalized === "estimate" || normalized === "modeled") {
    return "estimated";
  }

  if (normalized === "suppressed" || normalized === "redacted") {
    return "suppressed";
  }

  return "unknown";
}

function parseNumber(value: unknown): number | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  const normalized = normalizeString(value);
  if (!normalized) {
    return null;
  }

  const cleaned = normalized.replace(/,/g, "").replace(/%$/, "");
  if (/^(na|n\/a|null|undefined|missing)$/i.test(cleaned)) {
    return null;
  }

  const numeric = Number(cleaned);
  return Number.isFinite(numeric) ? numeric : null;
}

function fieldMap(fields: Record<string, unknown>): Map<string, FieldRead> {
  const mapped = new Map<string, FieldRead>();
  Object.entries(fields).forEach(([field, value]) => {
    const normalized = normalizeFieldName(field);
    if (normalized && !mapped.has(normalized)) {
      mapped.set(normalized, { field, value });
    }
  });
  return mapped;
}

function readField(fields: Map<string, FieldRead>, aliases: string[]): FieldRead | null {
  for (const alias of aliases) {
    const value = fields.get(alias);
    if (value && normalizeString(value.value) !== undefined) {
      return value;
    }
  }

  return null;
}

function detectFormat(input: AggregateTimeSeriesUploadInput): TimeSeriesUploadFormat | null {
  if (input.format) {
    return input.format;
  }

  const extension = input.fileName?.split(".").pop()?.toLowerCase();
  if (extension === "csv" || extension === "json") {
    return extension;
  }

  const firstCharacter = input.content.trimStart()[0];
  if (firstCharacter === "{" || firstCharacter === "[") {
    return "json";
  }

  if (input.content.includes(",")) {
    return "csv";
  }

  return null;
}

function parseCsvMatrix(content: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let index = 0; index < content.length; index += 1) {
    const char = content[index];
    const nextChar = content[index + 1];

    if (inQuotes) {
      if (char === "\"" && nextChar === "\"") {
        field += "\"";
        index += 1;
      } else if (char === "\"") {
        inQuotes = false;
      } else {
        field += char;
      }
      continue;
    }

    if (char === "\"") {
      inQuotes = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else if (char === "\r") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
      if (nextChar === "\n") {
        index += 1;
      }
    } else {
      field += char;
    }
  }

  if (inQuotes) {
    throw new Error("CSV has an unterminated quoted field.");
  }

  row.push(field);
  rows.push(row);

  return rows.filter((candidate) => candidate.some((cell) => cell.trim().length > 0));
}

function parseCsvUpload(input: AggregateTimeSeriesUploadInput): ParsedUpload {
  const issues: AggregateTimeSeriesValidationIssue[] = [];
  const matrix = parseCsvMatrix(input.content);

  if (matrix.length === 0) {
    return { rows: [], format: "csv", issues };
  }

  const headers = matrix[0].map((header) => header.trim());
  if (headers.length === 0 || headers.every((header) => header.length === 0)) {
    issues.push({
      severity: "error",
      code: "missing_header",
      message: "CSV uploads must include a header row."
    });
    return { rows: [], format: "csv", issues };
  }

  const rows = matrix.slice(1).map((cells, index) => {
    const fields: Record<string, unknown> = {};
    headers.forEach((header, headerIndex) => {
      fields[header || `column_${headerIndex + 1}`] = cells[headerIndex] ?? "";
    });

    if (cells.length > headers.length) {
      issues.push({
        severity: "warning",
        code: "extra_columns",
        message: "CSV row has more columns than the header row; extra cells were ignored.",
        row: index + 2
      });
    }

    return {
      rowNumber: index + 2,
      fields
    };
  });

  return { rows, format: "csv", issues };
}

function extractJsonRows(parsed: unknown): { rows: unknown[]; datasetName?: string; sourceLabel?: string } | null {
  if (Array.isArray(parsed)) {
    return { rows: parsed };
  }

  if (!isObject(parsed)) {
    return null;
  }

  const datasetName = normalizeString(parsed.name) ?? normalizeString(parsed.datasetName) ?? normalizeString(parsed.title);
  const sourceLabel =
    normalizeString(parsed.sourceLabel) ??
    normalizeString(parsed.sourceName) ??
    (isObject(parsed.source) ? normalizeString(parsed.source.name) : normalizeString(parsed.source));

  for (const key of ["records", "data", "rows", "observations", "series"]) {
    const candidate = parsed[key];
    if (Array.isArray(candidate)) {
      return { rows: candidate, datasetName, sourceLabel };
    }
  }

  return null;
}

function parseJsonUpload(input: AggregateTimeSeriesUploadInput): ParsedUpload {
  const parsed = JSON.parse(input.content) as unknown;
  const extracted = extractJsonRows(parsed);

  if (!extracted) {
    return {
      rows: [],
      format: "json",
      issues: [
        {
          severity: "error",
          code: "parse_failed",
          message: "JSON uploads must be an array of records or an object with a records, data, rows, observations, or series array."
        }
      ]
    };
  }

  const rows = extracted.rows
    .map((row, index): SourceRow | null => {
      if (!isObject(row)) {
        return null;
      }

      return {
        rowNumber: index + 1,
        fields: row
      };
    })
    .filter((row): row is SourceRow => row !== null);

  return {
    rows,
    format: "json",
    sourceLabel: extracted.sourceLabel,
    datasetName: extracted.datasetName,
    issues: []
  };
}

function parseUpload(input: AggregateTimeSeriesUploadInput, format: TimeSeriesUploadFormat): ParsedUpload {
  try {
    return format === "csv" ? parseCsvUpload(input) : parseJsonUpload(input);
  } catch (error) {
    return {
      rows: [],
      format,
      issues: [
        {
          severity: "error",
          code: "parse_failed",
          message: error instanceof Error ? error.message : "Upload could not be parsed."
        }
      ]
    };
  }
}

function titleFromFieldName(field: string | undefined): string {
  if (!field) {
    return "value";
  }

  return normalizeFieldName(field).replace(/_/g, " ") || "value";
}

function slug(value: string): string {
  const normalized = normalizeFieldName(value);
  return normalized.length > 0 ? normalized : "aggregate";
}

function buildSeriesLabel(parts: Array<string | undefined>): string {
  const labelParts = parts.filter((part): part is string => Boolean(part));
  return labelParts.length > 0 ? labelParts.join(" / ") : "Aggregate";
}

function hashString(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(index);
    hash |= 0;
  }

  return Math.abs(hash).toString(36);
}

function fileNameWithoutExtension(fileName: string | undefined): string | undefined {
  if (!fileName) {
    return undefined;
  }

  return fileName.replace(/\.[^.]+$/, "");
}

function findPrivacyRiskFields(rows: SourceRow[]): string[] {
  const riskyFields = new Set<string>();
  rows.forEach((row) => {
    Object.keys(row.fields).forEach((field) => {
      const normalized = normalizeFieldName(field);
      if (PRIVACY_RISK_FIELDS.has(normalized)) {
        riskyFields.add(field);
      }
    });
  });

  return [...riskyFields].sort();
}

function findLegacyPrivacyRiskFields(rows: Record<string, unknown>[]): string[] {
  const riskyFields = new Set<string>();
  rows.forEach((row) => {
    Object.keys(row).forEach((field) => {
      const normalized = normalizeFieldName(field);
      if (PRIVACY_RISK_FIELDS.has(normalized)) {
        riskyFields.add(field);
      }
    });
  });

  return [...riskyFields].sort();
}

function summarizeMetrics(records: AggregateTimeSeriesRecord[]): AggregateTimeSeriesMetricSummary[] {
  const summaries = new Map<string, AggregateTimeSeriesMetricSummary>();

  records.forEach((record) => {
    const current = summaries.get(record.metric);
    if (!current) {
      summaries.set(record.metric, {
        metric: record.metric,
        unit: record.unit,
        count: 1,
        min: record.value,
        max: record.value,
        firstDate: record.date,
        lastDate: record.date
      });
      return;
    }

    current.count += 1;
    current.min = Math.min(current.min, record.value);
    current.max = Math.max(current.max, record.value);
    current.firstDate = current.firstDate.localeCompare(record.date) <= 0 ? current.firstDate : record.date;
    current.lastDate = current.lastDate.localeCompare(record.date) >= 0 ? current.lastDate : record.date;
    if (!current.unit && record.unit) {
      current.unit = record.unit;
    }
  });

  return [...summaries.values()].sort((a, b) => a.metric.localeCompare(b.metric));
}

function normalizeRows(
  parsed: ParsedUpload,
  input: AggregateTimeSeriesUploadInput
): Omit<AggregateTimeSeriesNormalizationResult, "dataset"> & { records: AggregateTimeSeriesRecord[] } {
  const issues: AggregateTimeSeriesValidationIssue[] = [...parsed.issues];
  const records: AggregateTimeSeriesRecord[] = [];
  const seenRecords = new Set<string>();
  let rejectedRows = 0;

  const privacyRiskFields = findPrivacyRiskFields(parsed.rows);
  if (privacyRiskFields.length > 0) {
    issues.push({
      severity: "error",
      code: "privacy_risk",
      message: `Aggregate uploads cannot include likely individual identifier fields: ${privacyRiskFields.join(", ")}.`
    });
    return {
      records: [],
      issues,
      acceptedRows: 0,
      rejectedRows: parsed.rows.length
    };
  }

  parsed.rows.forEach((row) => {
    const fields = fieldMap(row.fields);
    const dateField = readField(fields, DATE_FIELD_ALIASES);
    const valueField = readField(fields, VALUE_FIELD_ALIASES);

    if (!dateField) {
      rejectedRows += 1;
      issues.push({
        severity: "error",
        code: "missing_required_field",
        message: "Row is missing a date field.",
        row: row.rowNumber,
        field: "date"
      });
      return;
    }

    const date = normalizeDateInput(dateField.value);
    if (!date) {
      rejectedRows += 1;
      issues.push({
        severity: "error",
        code: "invalid_date",
        message: "Date must be a valid calendar date.",
        row: row.rowNumber,
        field: dateField.field
      });
      return;
    }

    if (!valueField) {
      rejectedRows += 1;
      issues.push({
        severity: "error",
        code: "missing_required_field",
        message: "Row is missing a numeric value field.",
        row: row.rowNumber,
        field: "value"
      });
      return;
    }

    const value = parseNumber(valueField.value);
    if (value === null) {
      rejectedRows += 1;
      issues.push({
        severity: "error",
        code: "invalid_value",
        message: "Value must be numeric.",
        row: row.rowNumber,
        field: valueField.field
      });
      return;
    }

    const metric = normalizeString(readField(fields, METRIC_FIELD_ALIASES)?.value) ?? titleFromFieldName(valueField.field);
    const unit = normalizeString(readField(fields, UNIT_FIELD_ALIASES)?.value);
    const geographyId = normalizeString(readField(fields, GEOGRAPHY_ID_FIELD_ALIASES)?.value);
    const geographyName = normalizeString(readField(fields, GEOGRAPHY_NAME_FIELD_ALIASES)?.value);
    const pathogenId = normalizeString(readField(fields, PATHOGEN_ID_FIELD_ALIASES)?.value);
    const pathogenName = normalizeString(readField(fields, PATHOGEN_NAME_FIELD_ALIASES)?.value);
    const sourceLabel =
      normalizeString(readField(fields, SOURCE_FIELD_ALIASES)?.value) ??
      parsed.sourceLabel ??
      input.datasetName ??
      fileNameWithoutExtension(input.fileName);
    const quality = normalizeQuality(readField(fields, QUALITY_FIELD_ALIASES)?.value);

    let lower = parseNumber(readField(fields, LOWER_FIELD_ALIASES)?.value);
    let upper = parseNumber(readField(fields, UPPER_FIELD_ALIASES)?.value);
    if (lower !== null || upper !== null) {
      if (lower === null || upper === null || lower > upper) {
        issues.push({
          severity: "warning",
          code: "invalid_bound",
          message: "Uncertainty bounds were ignored because lower and upper values were incomplete or reversed.",
          row: row.rowNumber
        });
        lower = null;
        upper = null;
      }
    }

    const seriesLabel = buildSeriesLabel([geographyName ?? geographyId, pathogenName ?? pathogenId, sourceLabel]);
    const seriesKey = slug(seriesLabel);
    const duplicateKey = `${date}|${metric}|${seriesKey}`;
    if (seenRecords.has(duplicateKey)) {
      rejectedRows += 1;
      issues.push({
        severity: "error",
        code: "duplicate_record",
        message: "Duplicate aggregate records for the same date, metric, and series are not accepted.",
        row: row.rowNumber
      });
      return;
    }

    seenRecords.add(duplicateKey);
    records.push({
      id: `${date}-${slug(metric)}-${seriesKey}`,
      date,
      value,
      metric,
      seriesKey,
      seriesLabel,
      unit,
      geographyId,
      geographyName,
      pathogenId,
      pathogenName,
      sourceLabel,
      lower: lower ?? undefined,
      upper: upper ?? undefined,
      quality
    });
  });

  return {
    records: sortAggregateRecordsByDate(records),
    issues,
    acceptedRows: records.length,
    rejectedRows
  };
}

export function normalizeTimeSeriesUpload(input: AggregateTimeSeriesUploadInput): AggregateTimeSeriesNormalizationResult {
  if (!input.content.trim()) {
    const issue: AggregateTimeSeriesValidationIssue = {
      severity: "error",
      code: "empty_upload",
      message: "Upload content is empty."
    };
    return { dataset: null, issues: [issue], acceptedRows: 0, rejectedRows: 0 };
  }

  const format = detectFormat(input);
  if (!format) {
    const issue: AggregateTimeSeriesValidationIssue = {
      severity: "error",
      code: "unsupported_format",
      message: "Upload format could not be detected. Use a CSV or JSON file."
    };
    return { dataset: null, issues: [issue], acceptedRows: 0, rejectedRows: 0 };
  }

  const parsed = parseUpload(input, format);
  const normalized = normalizeRows(parsed, input);

  if (normalized.records.length === 0) {
    const issues =
      normalized.issues.length > 0
        ? normalized.issues
        : [
            {
              severity: "error" as const,
              code: "empty_upload" as const,
              message: "No valid aggregate time-series records were found."
            }
          ];

    return {
      dataset: null,
      issues,
      acceptedRows: 0,
      rejectedRows: normalized.rejectedRows
    };
  }

  const dateRange = getAggregateRecordDateRange(normalized.records);
  const uploadedAt = new Date().toISOString();
  const name =
    input.datasetName ??
    parsed.datasetName ??
    fileNameWithoutExtension(input.fileName) ??
    "Uploaded time series";
  const metadata: AggregateTimeSeriesDatasetMetadata = {
    id: `ts-${hashString(`${name}|${input.fileName ?? ""}|${uploadedAt}|${normalized.records.length}`)}`,
    name,
    uploadedAt,
    format,
    fileName: input.fileName,
    sourceLabel: parsed.sourceLabel,
    rowCount: parsed.rows.length
  };

  const dataset: AggregateTimeSeriesDataset = {
    metadata,
    records: normalized.records,
    metrics: summarizeMetrics(normalized.records),
    dateRange: dateRange ?? {
      startDate: normalized.records[0].date,
      endDate: normalized.records[normalized.records.length - 1].date
    },
    validation: {
      issues: normalized.issues,
      acceptedRows: normalized.acceptedRows,
      rejectedRows: normalized.rejectedRows
    },
    hasUncertainty: normalized.records.some((record) => record.lower !== undefined && record.upper !== undefined)
  };

  return {
    dataset,
    issues: normalized.issues,
    acceptedRows: normalized.acceptedRows,
    rejectedRows: normalized.rejectedRows
  };
}

function getStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function isPersistedDataset(value: unknown): value is AggregateTimeSeriesDataset {
  return (
    isObject(value) &&
    isObject(value.metadata) &&
    Array.isArray(value.records) &&
    Array.isArray(value.metrics) &&
    isObject(value.dateRange) &&
    isObject(value.validation)
  );
}

export function saveTimeSeriesDataset(
  dataset: AggregateTimeSeriesDataset,
  storageKey = DEFAULT_TIME_SERIES_STORAGE_KEY
): AggregateTimeSeriesPersistenceResult {
  const storage = getStorage();
  if (!storage) {
    return {
      ok: false,
      issue: {
        severity: "warning",
        code: "storage_unavailable",
        message: "localStorage is not available; the dataset was kept in memory only."
      }
    };
  }

  try {
    storage.setItem(storageKey, JSON.stringify(dataset));
    return { ok: true };
  } catch {
    return {
      ok: false,
      issue: {
        severity: "warning",
        code: "storage_failed",
        message: "The normalized dataset could not be persisted to localStorage."
      }
    };
  }
}

export function loadPersistedTimeSeriesDataset(storageKey = DEFAULT_TIME_SERIES_STORAGE_KEY): AggregateTimeSeriesDataset | null {
  const storage = getStorage();
  if (!storage) {
    return null;
  }

  const serialized = storage.getItem(storageKey);
  if (!serialized) {
    return null;
  }

  try {
    const parsed = JSON.parse(serialized) as unknown;
    return isPersistedDataset(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function clearPersistedTimeSeriesDataset(storageKey = DEFAULT_TIME_SERIES_STORAGE_KEY): AggregateTimeSeriesPersistenceResult {
  const storage = getStorage();
  if (!storage) {
    return {
      ok: false,
      issue: {
        severity: "warning",
        code: "storage_unavailable",
        message: "localStorage is not available."
      }
    };
  }

  try {
    storage.removeItem(storageKey);
    return { ok: true };
  } catch {
    return {
      ok: false,
      issue: {
        severity: "warning",
        code: "storage_failed",
        message: "The persisted dataset could not be removed from localStorage."
      }
    };
  }
}

function parseLegacyCsv(text: string): Record<string, string>[] {
  const matrix = parseCsvMatrix(text);
  if (matrix.length < 2) {
    return [];
  }

  const headers = matrix[0].map((header) => header.trim());
  return matrix.slice(1).map((cells) =>
    Object.fromEntries(headers.map((header, index) => [header, cells[index] ?? ""]))
  );
}

function normalizeLegacyRow(
  row: Record<string, unknown>,
  fallbackSourceId: string
): { record?: TimeSeriesRecord; error?: string; warning?: string } {
  const get = (key: string) => row[key] ?? row[key.toLowerCase()] ?? row[key.toUpperCase()];
  const date = String(get("date") ?? "").trim();
  const metric = String(get("metric") ?? "").trim();
  const value = parseNumber(get("value"));
  const countryRaw = String(get("countryIso3") ?? get("country") ?? get("countryName") ?? "").trim();
  const countryIso3 = normalizeIso3(countryRaw);

  const missing = LEGACY_REQUIRED_FIELDS.filter((field) => !String(get(field) ?? "").trim());
  if (missing.length > 0) {
    return { error: `Missing required field(s): ${missing.join(", ")}.` };
  }
  if (value === null) {
    return { error: `Invalid numeric value for ${metric || "record"}.` };
  }
  if (!countryIso3) {
    return { error: "Missing or unmappable countryIso3 / country name." };
  }
  if (!normalizeDateInput(date)) {
    return { error: `Invalid date "${date}". Use YYYY-MM-DD.` };
  }

  const latitude = parseNumber(get("latitude"));
  const longitude = parseNumber(get("longitude"));

  return {
    record: {
      sourceId: String(get("sourceId") ?? fallbackSourceId),
      countryIso3,
      date: normalizeDateInput(date) ?? date,
      metric,
      value,
      unit: String(get("unit") ?? "").trim(),
      locationName: String(get("locationName") ?? "").trim() || undefined,
      latitude: latitude ?? undefined,
      longitude: longitude ?? undefined,
      admin1: String(get("admin1") ?? "").trim() || undefined,
      admin2: String(get("admin2") ?? "").trim() || undefined,
      provenance: String(get("provenance") ?? "").trim() || undefined,
      notes: String(get("notes") ?? "").trim() || undefined
    }
  };
}

export function normalizeUploadedTimeSeries(
  text: string,
  fileName: string,
  fallbackSourceId: string
): TimeSeriesValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  let rows: Record<string, unknown>[] = [];

  try {
    if (fileName.toLowerCase().endsWith(".json")) {
      const parsed = JSON.parse(text) as unknown;
      rows = Array.isArray(parsed) ? (parsed as Record<string, unknown>[]) : [];
      if (!Array.isArray(parsed)) {
        errors.push("JSON upload must be an array of records.");
      }
    } else if (fileName.toLowerCase().endsWith(".csv")) {
      rows = parseLegacyCsv(text);
    } else {
      errors.push("Only CSV and JSON uploads are supported.");
    }
  } catch (error) {
    errors.push(error instanceof Error ? error.message : "Unable to parse uploaded file.");
  }

  const privacyRiskFields = findLegacyPrivacyRiskFields(rows);
  if (privacyRiskFields.length > 0) {
    errors.push(`Aggregate uploads cannot include likely individual, medical-record, or precise personal trace fields: ${privacyRiskFields.join(", ")}.`);
    return { records: [], errors, warnings };
  }

  const records: TimeSeriesRecord[] = [];
  rows.forEach((row, index) => {
    const normalized = normalizeLegacyRow(row, fallbackSourceId);
    if (normalized.record) {
      records.push(normalized.record);
    }
    if (normalized.error) {
      errors.push(`Row ${index + 1}: ${normalized.error}`);
    }
    if (normalized.warning) {
      warnings.push(`Row ${index + 1}: ${normalized.warning}`);
    }
  });

  if (records.length === 0 && errors.length === 0) {
    errors.push("No records found in upload.");
  }
  return { records, errors, warnings };
}

export const timeSeriesUploadAdapter = {
  loadDatasets(): UploadedDataset[] {
    return readJsonFromLocalStorage<UploadedDataset[]>(LEGACY_DATASETS_KEY, []);
  },

  saveDatasets(datasets: UploadedDataset[]): void {
    writeJsonToLocalStorage(LEGACY_DATASETS_KEY, datasets);
  },

  createDataset(
    fileName: string,
    sourceId: string,
    sourceName: string,
    records: TimeSeriesRecord[],
    warnings: string[]
  ): UploadedDataset {
    return {
      id: `dataset-${Date.now()}`,
      sourceId,
      sourceName,
      fileName,
      records,
      uploadedAt: new Date().toISOString(),
      validationWarnings: warnings
    };
  }
};
