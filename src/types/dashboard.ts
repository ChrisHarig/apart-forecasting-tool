import type { CountryNewsSummary } from "./news";
import type { DataSourceMetadata } from "./source";
import type { DateRangeState, UploadedDataset as TimeSeriesUploadedDataset } from "./timeseries";

export interface DashboardDataStatus {
  loading: boolean;
  error: string | null;
  lastLoadedAt?: string | null;
  stale?: boolean;
}

export type DashboardCurrentView = "world" | "sources" | "timeseries";
export type DashboardView = DashboardCurrentView;

export interface DashboardSelectedCountry {
  iso3: string;
  isoNumeric?: string;
  name: string;
}

export type SelectedCountry = DashboardSelectedCountry;

export type DashboardSourceKind =
  | "case-surveillance"
  | "forecast"
  | "laboratory"
  | "mobility"
  | "news"
  | "population"
  | "reference"
  | "transport"
  | "wastewater";

export type DashboardSourceRegistryStatus = "candidate" | "ready" | "loaded" | "error" | "disabled";
export type DashboardSourceTrust = "official" | "community" | "team-upload" | "reference";

export interface DashboardSourceRegistryEntry {
  id: string;
  sourceName: string;
  kind: DashboardSourceKind;
  status: DashboardSourceRegistryStatus;
  enabled: boolean;
  supportsUpload: boolean;
  trust: DashboardSourceTrust;
  requiredFields: readonly string[];
  optionalFields?: readonly string[];
  adapterId?: string;
  provenanceUrl?: string;
  lastUpdatedAt?: string | null;
  limitations?: string;
}

export type UploadedDatasetStatus = "queued" | "normalizing" | "ready" | "error";

export interface UploadedDatasetNormalizationAssumptions {
  dateField: string;
  valueField: string;
  sourceField?: string;
  countryField?: string;
  dateFormat: "iso" | "yyyy-mm-dd" | "detected";
  countryCodeFormat?: "iso2" | "iso3" | "iso-numeric" | "name";
  numericFields: readonly string[];
  missingValuePolicy: "drop-row" | "null" | "zero-fill";
}

export interface UploadedDatasetRecord {
  date: string;
  sourceId: string;
  metricName: string;
  value: number;
  countryIso3?: string;
  qualityFlags?: readonly string[];
}

export interface UploadedDataset {
  id: string;
  fileName: string;
  sourceId: string;
  kind: DashboardSourceKind;
  uploadedAt: string;
  status: UploadedDatasetStatus;
  rowCount: number;
  normalizedRowCount: number;
  rejectedRowCount: number;
  assumptions: UploadedDatasetNormalizationAssumptions;
  errors?: readonly string[];
}

export type DashboardNewsIngestionStatus = "disabled" | "idle" | "loading" | "ready" | "error";

export interface DashboardNewsStatus {
  enabled: boolean;
  status: DashboardNewsIngestionStatus;
  sourceIds: readonly string[];
  lastCheckedAt: string | null;
  articleCount: number;
  error: string | null;
  terms: readonly string[];
}

export interface DashboardDateRange {
  startDate: string | null;
  endDate: string | null;
}

export interface DashboardStateDraft {
  version: 1;
  currentView: DashboardCurrentView;
  selectedCountry: DashboardSelectedCountry | null;
  selectedSourceIds: readonly string[];
  sourceRegistry: readonly DashboardSourceRegistryEntry[];
  uploadedDatasets: readonly UploadedDataset[];
  news: DashboardNewsStatus;
  dateRange: DashboardDateRange;
  dataStatus: DashboardDataStatus;
}

export interface DashboardStateShape {
  currentView: DashboardCurrentView;
  selectedCountry: DashboardSelectedCountry | null;
  sourceCatalog: DataSourceMetadata[];
  userAddedSources: DataSourceMetadata[];
  uploadedDatasets: TimeSeriesUploadedDataset[];
  activeTimeSeriesSourceId: string | null;
  activeMetric: string | null;
  activeDateRange: DateRangeState;
  newsByCountry: Record<string, CountryNewsSummary>;
}
