export type DateRangePreset = "14d" | "1m" | "3m" | "6m" | "1y" | "2y" | "custom";

export interface TimeSeriesRecord {
  sourceId: string;
  countryIso3: string;
  date: string;
  metric: string;
  value: number;
  unit: string;
  locationName?: string;
  latitude?: number;
  longitude?: number;
  admin1?: string;
  admin2?: string;
  provenance?: string;
  notes?: string;
}

export interface UploadedDataset {
  id: string;
  sourceId: string;
  sourceName: string;
  fileName: string;
  records: TimeSeriesRecord[];
  uploadedAt: string;
  validationWarnings: string[];
}

export interface TimeSeriesValidationResult {
  records: TimeSeriesRecord[];
  errors: string[];
  warnings: string[];
}

export interface DateRangeState {
  preset: DateRangePreset;
  customStart?: string;
  customEnd?: string;
}

export type TimeSeriesAvailabilityStatus = "local" | "backend" | "local_and_backend" | "empty" | "error";

export interface AvailableTimeSeriesOption {
  countryIso3: string;
  sourceId: string;
  sourceName: string;
  metric: string;
  unit?: string;
  recordCount: number;
  firstDate: string;
  lastDate: string;
  provenance: "local_upload" | "backend" | "mixed";
  statusNote: string;
}

export interface TimeSeriesAvailabilityResult {
  countryIso3: string;
  options: AvailableTimeSeriesOption[];
  records: TimeSeriesRecord[];
  status: TimeSeriesAvailabilityStatus;
  error?: string;
}

export interface TimeSeriesRecordsSelection {
  countryIso3: string;
  sourceId?: string | null;
  metric?: string | null;
  dateRange?: DateRangeState;
  records: TimeSeriesRecord[];
}

export type TimeSeriesUploadFormat = "csv" | "json";

export type AggregateTimeSeriesIssueSeverity = "error" | "warning";

export type AggregateTimeSeriesIssueCode =
  | "empty_upload"
  | "unsupported_format"
  | "parse_failed"
  | "missing_header"
  | "missing_required_field"
  | "invalid_date"
  | "invalid_value"
  | "invalid_bound"
  | "duplicate_record"
  | "extra_columns"
  | "privacy_risk"
  | "storage_unavailable"
  | "storage_failed";

export type AggregateTimeSeriesValueQuality = "reported" | "estimated" | "suppressed" | "unknown";

export interface AggregateTimeSeriesDateRange {
  startDate: string;
  endDate: string;
}

export interface AggregateTimeSeriesDateRangeSelection {
  startDate?: string;
  endDate?: string;
}

export interface AggregateTimeSeriesRecord {
  id: string;
  date: string;
  value: number;
  metric: string;
  seriesKey: string;
  seriesLabel: string;
  unit?: string;
  geographyId?: string;
  geographyName?: string;
  pathogenId?: string;
  pathogenName?: string;
  sourceLabel?: string;
  lower?: number;
  upper?: number;
  quality?: AggregateTimeSeriesValueQuality;
}

export interface AggregateTimeSeriesMetricSummary {
  metric: string;
  unit?: string;
  count: number;
  min: number;
  max: number;
  firstDate: string;
  lastDate: string;
}

export interface AggregateTimeSeriesValidationIssue {
  severity: AggregateTimeSeriesIssueSeverity;
  code: AggregateTimeSeriesIssueCode;
  message: string;
  row?: number;
  field?: string;
}

export interface AggregateTimeSeriesValidationSummary {
  issues: AggregateTimeSeriesValidationIssue[];
  acceptedRows: number;
  rejectedRows: number;
}

export interface AggregateTimeSeriesDatasetMetadata {
  id: string;
  name: string;
  uploadedAt: string;
  format: TimeSeriesUploadFormat;
  fileName?: string;
  sourceLabel?: string;
  rowCount: number;
}

export interface AggregateTimeSeriesDataset {
  metadata: AggregateTimeSeriesDatasetMetadata;
  records: AggregateTimeSeriesRecord[];
  metrics: AggregateTimeSeriesMetricSummary[];
  dateRange: AggregateTimeSeriesDateRange;
  validation: AggregateTimeSeriesValidationSummary;
  hasUncertainty: boolean;
}

export interface AggregateTimeSeriesUploadInput {
  content: string;
  fileName?: string;
  format?: TimeSeriesUploadFormat;
  datasetName?: string;
}

export interface AggregateTimeSeriesNormalizationResult {
  dataset: AggregateTimeSeriesDataset | null;
  issues: AggregateTimeSeriesValidationIssue[];
  acceptedRows: number;
  rejectedRows: number;
}

export interface AggregateTimeSeriesPersistenceResult {
  ok: boolean;
  issue?: AggregateTimeSeriesValidationIssue;
}
