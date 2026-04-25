import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { countryNewsAdapter } from "../data/adapters/countryNewsAdapter";
import { sourceRegistryAdapter } from "../data/adapters/sourceRegistryAdapter";
import { timeSeriesUploadAdapter } from "../data/adapters/timeSeriesUploadAdapter";
import type { DashboardView, SelectedCountry } from "../types/dashboard";
import type { CountryNewsSummary } from "../types/news";
import type { AddSourceInput, DataSourceMetadata, SourceValidationResult } from "../types/source";
import type { DateRangeState, UploadedDataset } from "../types/timeseries";

export const DEFAULT_SELECTED_COUNTRY: SelectedCountry = {
  iso3: "USA",
  isoNumeric: "840",
  name: "United States"
};

export function applyCountrySelection(currentView: DashboardView, country: SelectedCountry | null) {
  return {
    view: currentView,
    selectedCountry: country
  };
}

interface DashboardContextValue {
  view: DashboardView;
  setView: (view: DashboardView) => void;
  selectedCountry: SelectedCountry | null;
  setSelectedCountry: (country: SelectedCountry | null) => void;
  hoverCountry: SelectedCountry | null;
  setHoverCountry: (country: SelectedCountry | null) => void;
  sources: DataSourceMetadata[];
  userAddedSources: DataSourceMetadata[];
  addUserSource: (input: AddSourceInput) => SourceValidationResult;
  uploadedDatasets: UploadedDataset[];
  addUploadedDataset: (dataset: UploadedDataset) => void;
  activeTimeSeriesSourceId: string | null;
  setActiveTimeSeriesSourceId: (sourceId: string | null) => void;
  activeMetric: string | null;
  setActiveMetric: (metric: string | null) => void;
  activeDateRange: DateRangeState;
  setActiveDateRange: (range: DateRangeState) => void;
  newsByCountry: Record<string, CountryNewsSummary>;
  loadNewsForCountry: (countryIso3: string) => Promise<void>;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<DashboardView>("world");
  const [selectedCountry, setSelectedCountryState] = useState<SelectedCountry | null>(DEFAULT_SELECTED_COUNTRY);
  const [hoverCountry, setHoverCountryState] = useState<SelectedCountry | null>(null);
  const [userAddedSources, setUserAddedSources] = useState<DataSourceMetadata[]>(() => sourceRegistryAdapter.loadUserSources());
  const [uploadedDatasets, setUploadedDatasets] = useState<UploadedDataset[]>(() => timeSeriesUploadAdapter.loadDatasets());
  const [activeTimeSeriesSourceId, setActiveTimeSeriesSourceId] = useState<string | null>(null);
  const [activeMetric, setActiveMetric] = useState<string | null>(null);
  const [activeDateRange, setActiveDateRange] = useState<DateRangeState>({ preset: "3m" });
  const [newsByCountry, setNewsByCountry] = useState<Record<string, CountryNewsSummary>>({});

  const sources = useMemo(() => [...sourceRegistryAdapter.listBaseSources(), ...userAddedSources], [userAddedSources]);

  const loadNewsForCountry = useCallback(
    async (countryIso3: string) => {
      if (newsByCountry[countryIso3]?.status === "ready" || newsByCountry[countryIso3]?.status === "loading") return;
      setNewsByCountry((current) => ({
        ...current,
        [countryIso3]: { countryIso3, status: "loading", items: [] }
      }));
      const summary = await countryNewsAdapter.getLatestForCountry(countryIso3);
      setNewsByCountry((current) => ({ ...current, [countryIso3]: summary }));
    },
    [newsByCountry]
  );

  const setSelectedCountry = useCallback(
    (country: SelectedCountry | null) => {
      const next = applyCountrySelection(view, country);
      setSelectedCountryState(next.selectedCountry);
      if (country) {
        void loadNewsForCountry(country.iso3);
      }
    },
    [loadNewsForCountry, view]
  );

  const setHoverCountry = useCallback(
    (country: SelectedCountry | null) => {
      setHoverCountryState(country);
      if (country) {
        void loadNewsForCountry(country.iso3);
      }
    },
    [loadNewsForCountry]
  );

  const addUserSource = useCallback((input: AddSourceInput): SourceValidationResult => {
    const result = sourceRegistryAdapter.addUserSource(input);
    if (result.source) {
      const next = sourceRegistryAdapter.loadUserSources();
      setUserAddedSources(next);
      setActiveTimeSeriesSourceId(result.source.id);
    }
    return result.validation;
  }, []);

  const addUploadedDataset = useCallback((dataset: UploadedDataset) => {
    setUploadedDatasets((current) => {
      const next = [...current, dataset];
      timeSeriesUploadAdapter.saveDatasets(next);
      return next;
    });
    setActiveTimeSeriesSourceId(dataset.sourceId);
    const firstMetric = dataset.records[0]?.metric;
    if (firstMetric) setActiveMetric(firstMetric);
  }, []);

  const value = useMemo(
    () => ({
      view,
      setView,
      selectedCountry,
      setSelectedCountry,
      hoverCountry,
      setHoverCountry,
      sources,
      userAddedSources,
      addUserSource,
      uploadedDatasets,
      addUploadedDataset,
      activeTimeSeriesSourceId,
      setActiveTimeSeriesSourceId,
      activeMetric,
      setActiveMetric,
      activeDateRange,
      setActiveDateRange,
      newsByCountry,
      loadNewsForCountry
    }),
    [
      view,
      selectedCountry,
      hoverCountry,
      sources,
      userAddedSources,
      uploadedDatasets,
      activeTimeSeriesSourceId,
      activeMetric,
      activeDateRange,
      newsByCountry,
      setSelectedCountry,
      setHoverCountry,
      addUserSource,
      addUploadedDataset,
      loadNewsForCountry
    ]
  );

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) {
    throw new Error("useDashboard must be used within DashboardProvider");
  }
  return context;
}
