import { describe, expect, it } from "vitest";
import type {
  DashboardCurrentView,
  DashboardDateRange,
  DashboardNewsStatus,
  DashboardSourceKind,
  DashboardSourceRegistryEntry,
  DashboardSourceRegistryStatus,
  DashboardStateDraft,
  UploadedDataset,
  UploadedDatasetNormalizationAssumptions,
  UploadedDatasetRecord
} from "./dashboard";

const supportedCurrentViews = ["world", "sources", "timeseries"] satisfies DashboardCurrentView[];
const stateStorageKey = "sentinel-atlas.dashboard.v1";

interface SourceCatalogFixture {
  id: string;
  sourceName: string;
  dataType: string;
  relevance: string;
  likelyFields: string;
  limitations: string;
  mvpStatus: "include now" | "placeholder" | "later";
}

const sourceCatalogFixture: SourceCatalogFixture[] = [
  {
    id: "wastewaterscan",
    sourceName: "WastewaterSCAN",
    dataType: "Wastewater surveillance",
    relevance: "Early-warning signal layer and chart overlay for aggregate pathogen trends.",
    likelyFields: "site id, sample date, normalized concentration, trend flag, detection status",
    limitations: "Coverage varies by catchment and reporting lag.",
    mvpStatus: "placeholder"
  },
  {
    id: "cdc-nwss",
    sourceName: "CDC NWSS / wastewater program",
    dataType: "Wastewater surveillance",
    relevance: "Primary future source for wastewater panels in US-focused deployments.",
    likelyFields: "sample date, site, location, percentile, trend, viral activity level",
    limitations: "Public views can be transformed and delayed.",
    mvpStatus: "placeholder"
  },
  {
    id: "teammate-wastewater",
    sourceName: "Future teammate-provided wastewater dataset",
    dataType: "Wastewater surveillance",
    relevance: "Primary placeholder for teammate-provided wastewater adapter.",
    likelyFields: "date, geography, target, normalized signal, trend, quality flags",
    limitations: "Schema, lag, missingness, and QA rules must be documented before production display.",
    mvpStatus: "later"
  },
  {
    id: "ourairports",
    sourceName: "OurAirports",
    dataType: "Airport reference data",
    relevance: "Static reference layer for airport nodes and map context.",
    likelyFields: "airport id, name, IATA, ICAO, latitude, longitude, country",
    limitations: "Static reference data must be normalized before display.",
    mvpStatus: "include now"
  },
  {
    id: "portwatch",
    sourceName: "IMF PortWatch / UN AIS-derived port activity",
    dataType: "Port and cargo activity",
    relevance: "Future cargo/ferry/port movement context layer.",
    likelyFields: "port id, date, vessel arrivals, port calls, cargo activity index",
    limitations: "Use only aggregate activity indexes.",
    mvpStatus: "placeholder"
  }
];

function inferSourceKind(source: SourceCatalogFixture): DashboardSourceKind {
  const text = `${source.sourceName} ${source.dataType} ${source.relevance}`.toLowerCase();

  if (text.includes("wastewater")) return "wastewater";
  if (text.includes("forecast")) return "forecast";
  if (text.includes("laboratory")) return "laboratory";
  if (text.includes("airport") || text.includes("port") || text.includes("cargo") || text.includes("ferry")) return "transport";
  if (text.includes("mobility")) return "mobility";
  if (text.includes("population")) return "population";

  return "reference";
}

function inferRegistryStatus(source: SourceCatalogFixture): DashboardSourceRegistryStatus {
  return source.mvpStatus === "include now" ? "ready" : "candidate";
}

function registryFromCatalog(catalog: readonly SourceCatalogFixture[]): DashboardSourceRegistryEntry[] {
  return catalog.map((source) => ({
    id: source.id,
    sourceName: source.sourceName,
    kind: inferSourceKind(source),
    status: inferRegistryStatus(source),
    enabled: false,
    supportsUpload: source.id.startsWith("teammate-"),
    trust: source.id.startsWith("teammate-") ? "team-upload" : "official",
    requiredFields: source.likelyFields.split(",").map((field) => field.trim()),
    limitations: source.limitations
  }));
}

function filterSourceRegistry(
  registry: readonly DashboardSourceRegistryEntry[],
  filters: {
    kind?: DashboardSourceKind;
    status?: DashboardSourceRegistryStatus;
    query?: string;
    onlyEnabled?: boolean;
  }
) {
  const query = filters.query?.trim().toLowerCase();

  return registry.filter((source) => {
    const searchableText = `${source.sourceName} ${source.kind} ${source.limitations ?? ""}`.toLowerCase();

    return (
      (!filters.kind || source.kind === filters.kind) &&
      (!filters.status || source.status === filters.status) &&
      (!filters.onlyEnabled || source.enabled) &&
      (!query || searchableText.includes(query))
    );
  });
}

function defaultNewsStatus(): DashboardNewsStatus {
  return {
    enabled: false,
    status: "disabled",
    sourceIds: [],
    lastCheckedAt: null,
    articleCount: 0,
    error: null,
    terms: []
  };
}

function defaultDashboardState(): DashboardStateDraft {
  return {
    version: 1,
    currentView: "world",
    selectedCountry: null,
    selectedSourceIds: [],
    sourceRegistry: registryFromCatalog(sourceCatalogFixture),
    uploadedDatasets: [],
    news: defaultNewsStatus(),
    dateRange: { startDate: null, endDate: null },
    dataStatus: { loading: false, error: null, lastLoadedAt: null, stale: false }
  };
}

function createMemoryStorage(): Pick<Storage, "getItem" | "setItem" | "removeItem" | "clear"> {
  const values = new Map<string, string>();

  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => {
      values.set(key, value);
    },
    removeItem: (key) => {
      values.delete(key);
    },
    clear: () => {
      values.clear();
    }
  };
}

function persistDashboardState(storage: Pick<Storage, "setItem">, state: DashboardStateDraft) {
  storage.setItem(
    stateStorageKey,
    JSON.stringify({
      version: state.version,
      currentView: state.currentView,
      selectedCountry: state.selectedCountry,
      selectedSourceIds: state.selectedSourceIds,
      uploadedDatasets: state.uploadedDatasets,
      news: state.news,
      dateRange: state.dateRange
    })
  );
}

function restoreDashboardState(storage: Pick<Storage, "getItem">, fallback: DashboardStateDraft): DashboardStateDraft {
  const rawState = storage.getItem(stateStorageKey);
  if (!rawState) return fallback;

  try {
    const parsed = JSON.parse(rawState) as Partial<DashboardStateDraft>;
    if (parsed.version !== 1 || !supportedCurrentViews.includes(parsed.currentView as DashboardCurrentView)) {
      return fallback;
    }

    return {
      ...fallback,
      currentView: parsed.currentView as DashboardCurrentView,
      selectedCountry: parsed.selectedCountry ?? null,
      selectedSourceIds: Array.isArray(parsed.selectedSourceIds) ? parsed.selectedSourceIds : [],
      uploadedDatasets: Array.isArray(parsed.uploadedDatasets) ? parsed.uploadedDatasets : [],
      news: parsed.news ? { ...fallback.news, ...parsed.news } : fallback.news,
      dateRange: parsed.dateRange ? { ...fallback.dateRange, ...parsed.dateRange } : fallback.dateRange
    };
  } catch {
    return fallback;
  }
}

type RawUploadRow = Record<string, string | number | null | undefined>;

function normalizeDate(value: string | number | null | undefined) {
  const text = String(value ?? "").trim();
  const match = /^(?<year>\d{4})[-/](?<month>\d{2})[-/](?<day>\d{2})$/.exec(text);

  if (!match?.groups) return null;

  return `${match.groups.year}-${match.groups.month}-${match.groups.day}`;
}

function normalizeUploadedRows(
  rows: readonly RawUploadRow[],
  sourceId: string,
  assumptions: UploadedDatasetNormalizationAssumptions
) {
  const accepted: UploadedDatasetRecord[] = [];
  const rejected: Array<{ row: RawUploadRow; reason: string }> = [];

  for (const row of rows) {
    const date = normalizeDate(row[assumptions.dateField]);
    const value = Number(row[assumptions.valueField]);
    const countryIso3 = assumptions.countryField
      ? String(row[assumptions.countryField] ?? "")
          .trim()
          .toUpperCase()
      : undefined;

    if (!date) {
      rejected.push({ row, reason: "missing-date" });
      continue;
    }

    if (!Number.isFinite(value)) {
      rejected.push({ row, reason: "invalid-number" });
      continue;
    }

    if (assumptions.countryField && !countryIso3) {
      rejected.push({ row, reason: "missing-country" });
      continue;
    }

    accepted.push({
      date,
      sourceId,
      metricName: assumptions.valueField,
      value,
      countryIso3
    });
  }

  return { accepted, rejected };
}

function filterRecordsByDateRange(records: readonly UploadedDatasetRecord[], dateRange: DashboardDateRange) {
  return records.filter((record) => {
    return (
      (!dateRange.startDate || record.date >= dateRange.startDate) &&
      (!dateRange.endDate || record.date <= dateRange.endDate)
    );
  });
}

function selectRenderableRecords(state: DashboardStateDraft, records: readonly UploadedDatasetRecord[]) {
  const selectedSourceIds = new Set(state.selectedSourceIds);
  const enabledSourceIds = new Set(
    state.sourceRegistry.filter((source) => source.enabled && selectedSourceIds.has(source.id)).map((source) => source.id)
  );
  const readyDatasetSourceIds = new Set(
    state.uploadedDatasets.filter((dataset) => dataset.status === "ready").map((dataset) => dataset.sourceId)
  );

  return records.filter((record) => enabledSourceIds.has(record.sourceId) && readyDatasetSourceIds.has(record.sourceId));
}

describe("dashboard integration state draft", () => {
  it("defines the next dashboard views without relying on the legacy overview view", () => {
    expect(supportedCurrentViews).toEqual(["world", "sources", "timeseries"]);
  });

  it("filters source registry entries by source kind, readiness, and query", () => {
    const registry = registryFromCatalog(sourceCatalogFixture);

    expect(filterSourceRegistry(registry, { kind: "wastewater", status: "candidate" }).map((source) => source.id)).toEqual([
      "wastewaterscan",
      "cdc-nwss",
      "teammate-wastewater"
    ]);
    expect(filterSourceRegistry(registry, { status: "ready" }).map((source) => source.id)).toEqual(["ourairports"]);
    expect(filterSourceRegistry(registry, { query: "port activity" }).map((source) => source.id)).toEqual(["portwatch"]);
  });

  it("persists analyst state to localStorage-compatible storage and rejects stale versions", () => {
    const storage = createMemoryStorage();
    const dataset: UploadedDataset = {
      id: "upload-1",
      fileName: "wastewater.csv",
      sourceId: "teammate-wastewater",
      kind: "wastewater",
      uploadedAt: "2026-04-25T16:00:00.000Z",
      status: "ready",
      rowCount: 3,
      normalizedRowCount: 2,
      rejectedRowCount: 1,
      assumptions: {
        dateField: "sample_date",
        valueField: "normalized_signal",
        countryField: "country",
        dateFormat: "detected",
        countryCodeFormat: "iso3",
        numericFields: ["normalized_signal"],
        missingValuePolicy: "drop-row"
      }
    };
    const state: DashboardStateDraft = {
      ...defaultDashboardState(),
      currentView: "timeseries",
      selectedCountry: { iso3: "USA", isoNumeric: "840", name: "United States" },
      selectedSourceIds: ["teammate-wastewater"],
      uploadedDatasets: [dataset],
      news: {
        ...defaultNewsStatus(),
        enabled: true,
        status: "ready",
        sourceIds: ["public-health-news"],
        lastCheckedAt: "2026-04-25T16:30:00.000Z",
        articleCount: 4,
        terms: ["influenza"]
      },
      dateRange: { startDate: "2026-04-01", endDate: "2026-04-30" }
    };

    persistDashboardState(storage, state);

    const restored = restoreDashboardState(storage, defaultDashboardState());
    expect(restored.currentView).toBe("timeseries");
    expect(restored.selectedCountry?.iso3).toBe("USA");
    expect(restored.selectedSourceIds).toEqual(["teammate-wastewater"]);
    expect(restored.uploadedDatasets).toEqual([dataset]);
    expect(restored.news.articleCount).toBe(4);
    expect(restored.dateRange).toEqual({ startDate: "2026-04-01", endDate: "2026-04-30" });

    storage.setItem(stateStorageKey, JSON.stringify({ version: 2, currentView: "overview" }));
    expect(restoreDashboardState(storage, defaultDashboardState()).currentView).toBe("world");
  });

  it("normalizes uploaded rows by trimming countries, detecting ISO dates, and rejecting invalid metrics", () => {
    const assumptions: UploadedDatasetNormalizationAssumptions = {
      dateField: "sample_date",
      valueField: "normalized_signal",
      countryField: "country",
      dateFormat: "detected",
      countryCodeFormat: "iso3",
      numericFields: ["normalized_signal"],
      missingValuePolicy: "drop-row"
    };

    const result = normalizeUploadedRows(
      [
        { sample_date: "2026/04/05", country: " usa ", normalized_signal: "12.4" },
        { sample_date: "", country: "CAN", normalized_signal: "8" },
        { sample_date: "2026-04-06", country: "FRA", normalized_signal: "not-a-number" }
      ],
      "teammate-wastewater",
      assumptions
    );

    expect(result.accepted).toEqual([
      {
        date: "2026-04-05",
        sourceId: "teammate-wastewater",
        metricName: "normalized_signal",
        value: 12.4,
        countryIso3: "USA"
      }
    ]);
    expect(result.rejected.map((item) => item.reason)).toEqual(["missing-date", "invalid-number"]);
  });

  it("filters normalized upload records by an inclusive date range", () => {
    const records: UploadedDatasetRecord[] = [
      { date: "2026-03-31", sourceId: "teammate-wastewater", metricName: "normalized_signal", value: 7 },
      { date: "2026-04-01", sourceId: "teammate-wastewater", metricName: "normalized_signal", value: 8 },
      { date: "2026-04-15", sourceId: "teammate-wastewater", metricName: "normalized_signal", value: 10 },
      { date: "2026-05-01", sourceId: "teammate-wastewater", metricName: "normalized_signal", value: 11 }
    ];

    expect(filterRecordsByDateRange(records, { startDate: "2026-04-01", endDate: "2026-04-30" }).map((record) => record.date)).toEqual([
      "2026-04-01",
      "2026-04-15"
    ]);
  });

  it("does not expose renderable data from the default empty state", () => {
    const records: UploadedDatasetRecord[] = [
      { date: "2026-04-05", sourceId: "teammate-wastewater", metricName: "normalized_signal", value: 12.4 }
    ];

    expect(selectRenderableRecords(defaultDashboardState(), records)).toEqual([]);

    const stateWithReadyUpload: DashboardStateDraft = {
      ...defaultDashboardState(),
      selectedSourceIds: ["teammate-wastewater"],
      sourceRegistry: defaultDashboardState().sourceRegistry.map((source) =>
        source.id === "teammate-wastewater" ? { ...source, enabled: true, status: "loaded" } : source
      ),
      uploadedDatasets: [
        {
          id: "upload-1",
          fileName: "wastewater.csv",
          sourceId: "teammate-wastewater",
          kind: "wastewater",
          uploadedAt: "2026-04-25T16:00:00.000Z",
          status: "ready",
          rowCount: 1,
          normalizedRowCount: 1,
          rejectedRowCount: 0,
          assumptions: {
            dateField: "sample_date",
            valueField: "normalized_signal",
            countryField: "country",
            dateFormat: "detected",
            countryCodeFormat: "iso3",
            numericFields: ["normalized_signal"],
            missingValuePolicy: "drop-row"
          }
        }
      ]
    };

    expect(selectRenderableRecords(stateWithReadyUpload, records)).toEqual(records);
  });
});
