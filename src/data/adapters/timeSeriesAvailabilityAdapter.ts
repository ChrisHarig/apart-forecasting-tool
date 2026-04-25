import type {
  AggregateTimeSeriesDataset,
  AvailableTimeSeriesOption,
  DateRangeState,
  TimeSeriesAvailabilityResult,
  TimeSeriesRecord,
  TimeSeriesRecordsSelection,
  UploadedDataset
} from "../../types/timeseries";
import { normalizeIso3 } from "../../utils/countryCodes";
import { filterRecordsByDateRange } from "../../utils/dateRange";
import { loadPersistedTimeSeriesDataset, timeSeriesUploadAdapter } from "./timeSeriesUploadAdapter";

interface TimeSeriesAvailabilityOptions {
  uploadedDatasets?: UploadedDataset[];
  includeBackend?: boolean;
  apiBaseUrl?: string;
}

interface BackendRecordLike {
  [key: string]: unknown;
}

function normalizeApiBaseUrl(apiBaseUrl?: string): string | null {
  const value = apiBaseUrl ?? import.meta.env.VITE_SENTINEL_API_BASE_URL;
  if (!value?.trim()) return null;
  return value.replace(/\/+$/, "");
}

function stringValue(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const normalized = String(value).trim();
    if (normalized) return normalized;
  }

  return undefined;
}

function numericValue(...values: unknown[]): number | null {
  for (const value of values) {
    if (value === null || value === undefined || value === "") continue;
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }

  return null;
}

function normalizeDate(value: unknown): string | null {
  const raw = stringValue(value);
  if (!raw) return null;
  const parsed = new Date(raw);
  if (!Number.isNaN(parsed.getTime())) return parsed.toISOString().slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw : null;
}

function optionKey(sourceId: string, metric: string, countryIso3: string) {
  return `${countryIso3}::${sourceId}::${metric}`;
}

function buildSourceNameMap(datasets: UploadedDataset[]): Record<string, string> {
  return datasets.reduce<Record<string, string>>((sourceNames, dataset) => {
    sourceNames[dataset.sourceId] = dataset.sourceName;
    return sourceNames;
  }, {});
}

export function getUploadedDatasetRecords(datasets: UploadedDataset[]): TimeSeriesRecord[] {
  return datasets.flatMap((dataset) => dataset.records);
}

export function getPersistedAggregateRecords(dataset: AggregateTimeSeriesDataset | null = loadPersistedTimeSeriesDataset()): TimeSeriesRecord[] {
  if (!dataset) return [];

  return dataset.records
    .map((record): TimeSeriesRecord | null => {
      const countryIso3 = normalizeIso3(record.geographyId) ?? normalizeIso3(record.geographyName);
      if (!countryIso3) return null;
      return {
        sourceId: dataset.metadata.id,
        countryIso3,
        date: record.date,
        metric: record.metric,
        value: record.value,
        unit: record.unit ?? "",
        locationName: record.geographyName,
        provenance: record.sourceLabel ?? dataset.metadata.sourceLabel ?? dataset.metadata.name
      };
    })
    .filter((record): record is TimeSeriesRecord => Boolean(record));
}

export function normalizeBackendTimeSeriesRecord(record: BackendRecordLike): TimeSeriesRecord | null {
  const countryIso3 = normalizeIso3(stringValue(record.countryIso3, record.country_iso3, record.country, record.countryName, record.country_name));
  const sourceId = stringValue(record.sourceId, record.source_id, record.source, record.sourceName, record.source_name);
  const metric = stringValue(record.metric, record.metricName, record.metric_name, record.signalCategory, record.signal_category);
  const date = normalizeDate(record.date ?? record.observedAt ?? record.observed_at ?? record.reportedAt ?? record.reported_at);
  const value = numericValue(record.value, record.observed, record.estimate, record.count, record.rate);

  if (!countryIso3 || !sourceId || !metric || !date || value === null) return null;

  return {
    sourceId,
    countryIso3,
    date,
    metric,
    value,
    unit: stringValue(record.unit, record.units) ?? "",
    locationName: stringValue(record.locationName, record.location_name, record.admin1),
    latitude: numericValue(record.latitude, record.lat) ?? undefined,
    longitude: numericValue(record.longitude, record.lon, record.lng) ?? undefined,
    admin1: stringValue(record.admin1, record.admin_1),
    admin2: stringValue(record.admin2, record.admin_2),
    provenance: stringValue(record.provenance, record.provenanceUrl, record.provenance_url, record.sourceUrl, record.source_url),
    notes: stringValue(record.notes, record.note)
  };
}

function normalizeBackendRecords(payload: unknown): TimeSeriesRecord[] {
  const rows = Array.isArray(payload)
    ? payload
    : typeof payload === "object" && payload !== null && Array.isArray((payload as { records?: unknown[] }).records)
      ? (payload as { records: unknown[] }).records
      : [];

  return rows
    .map((row) => (typeof row === "object" && row !== null ? normalizeBackendTimeSeriesRecord(row as BackendRecordLike) : null))
    .filter((record): record is TimeSeriesRecord => Boolean(record));
}

export function deriveAvailableTimeSeriesOptions(
  records: TimeSeriesRecord[],
  countryIso3: string,
  sourceNames: Record<string, string> = {},
  provenance: AvailableTimeSeriesOption["provenance"] = "local_upload"
): AvailableTimeSeriesOption[] {
  const grouped = new Map<string, AvailableTimeSeriesOption>();

  records
    .filter((record) => record.countryIso3 === countryIso3)
    .forEach((record) => {
      const key = optionKey(record.sourceId, record.metric, record.countryIso3);
      const current = grouped.get(key);
      if (!current) {
        grouped.set(key, {
          countryIso3: record.countryIso3,
          sourceId: record.sourceId,
          sourceName: sourceNames[record.sourceId] ?? record.provenance ?? record.sourceId,
          metric: record.metric,
          unit: record.unit || undefined,
          recordCount: 1,
          firstDate: record.date,
          lastDate: record.date,
          provenance,
          statusNote: provenance === "backend" ? "Backend aggregate records." : "Local uploaded aggregate records."
        });
        return;
      }

      current.recordCount += 1;
      current.firstDate = current.firstDate.localeCompare(record.date) <= 0 ? current.firstDate : record.date;
      current.lastDate = current.lastDate.localeCompare(record.date) >= 0 ? current.lastDate : record.date;
      if (!current.unit && record.unit) current.unit = record.unit;
    });

  return [...grouped.values()].sort((a, b) => {
    const sourceCompare = a.sourceName.localeCompare(b.sourceName);
    return sourceCompare !== 0 ? sourceCompare : a.metric.localeCompare(b.metric);
  });
}

export function getTimeSeriesRecordsForSelection(selection: TimeSeriesRecordsSelection): TimeSeriesRecord[] {
  const records = selection.records.filter(
    (record) =>
      record.countryIso3 === selection.countryIso3 &&
      (!selection.sourceId || record.sourceId === selection.sourceId) &&
      (!selection.metric || record.metric === selection.metric)
  );

  const filtered = selection.dateRange ? filterRecordsByDateRange(records, selection.dateRange) : records;
  return filtered.sort((a, b) => a.date.localeCompare(b.date));
}

export function getLocalTimeSeriesAvailability(countryIso3: string, uploadedDatasets = timeSeriesUploadAdapter.loadDatasets()): TimeSeriesAvailabilityResult {
  const uploadedRecords = getUploadedDatasetRecords(uploadedDatasets);
  const aggregateRecords = getPersistedAggregateRecords();
  const records = [...uploadedRecords, ...aggregateRecords].filter((record) => record.countryIso3 === countryIso3);
  const sourceNames = {
    ...buildSourceNameMap(uploadedDatasets),
    ...Object.fromEntries(aggregateRecords.map((record) => [record.sourceId, record.provenance ?? record.sourceId]))
  };
  const options = deriveAvailableTimeSeriesOptions(records, countryIso3, sourceNames);

  return {
    countryIso3,
    options,
    records,
    status: options.length > 0 ? "local" : "empty"
  };
}

async function fetchBackendRecords(countryIso3: string, apiBaseUrl: string, dateRange?: DateRangeState): Promise<TimeSeriesRecord[]> {
  const availableUrl = `${apiBaseUrl}/api/countries/${encodeURIComponent(countryIso3)}/timeseries/available`;
  await fetch(availableUrl, { headers: { Accept: "application/json" } }).catch(() => undefined);

  const params = new URLSearchParams({ countryIso3 });
  if (dateRange?.customStart) params.set("startDate", dateRange.customStart);
  if (dateRange?.customEnd) params.set("endDate", dateRange.customEnd);
  const response = await fetch(`${apiBaseUrl}/api/timeseries?${params.toString()}`, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Backend time-series request failed with ${response.status}.`);
  return normalizeBackendRecords(await response.json());
}

export async function getAvailableTimeSeriesForCountry(
  countryIso3: string,
  options: TimeSeriesAvailabilityOptions = {}
): Promise<TimeSeriesAvailabilityResult> {
  const local = getLocalTimeSeriesAvailability(countryIso3, options.uploadedDatasets);
  const apiBaseUrl = normalizeApiBaseUrl(options.apiBaseUrl);

  if (!options.includeBackend || !apiBaseUrl) return local;

  try {
    const backendRecords = (await fetchBackendRecords(countryIso3, apiBaseUrl)).filter((record) => record.countryIso3 === countryIso3);
    const records = [...local.records, ...backendRecords];
    const localOptions = deriveAvailableTimeSeriesOptions(local.records, countryIso3, buildSourceNameMap(options.uploadedDatasets ?? []));
    const backendOptions = deriveAvailableTimeSeriesOptions(backendRecords, countryIso3, {}, "backend");
    return {
      countryIso3,
      options: [...localOptions, ...backendOptions],
      records,
      status: localOptions.length > 0 && backendOptions.length > 0 ? "local_and_backend" : backendOptions.length > 0 ? "backend" : local.status
    };
  } catch (error) {
    return {
      ...local,
      status: local.options.length > 0 ? local.status : "error",
      error: error instanceof Error ? error.message : "Backend time-series request failed."
    };
  }
}

export const timeSeriesAvailabilityAdapter = {
  getAvailableTimeSeriesForCountry,
  getLocalTimeSeriesAvailability,
  getTimeSeriesRecordsForSelection,
  deriveAvailableTimeSeriesOptions,
  getUploadedDatasetRecords,
  getPersistedAggregateRecords,
  normalizeBackendTimeSeriesRecord
};
