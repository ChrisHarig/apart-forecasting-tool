import { ShieldCheck } from "lucide-react";
import { SideNav, type SideNavItemId } from "../Navigation/SideNav";
import { WorldMap } from "../Map/WorldMap";
import { SourcesPage } from "../Sources/SourcesPage";
import { TimeSeriesPage } from "../TimeSeries/TimeSeriesPage";
import { useDashboard } from "../../state/DashboardContext";
import type { DashboardView } from "../../types/dashboard";
import { getSourcesForCountry } from "../../data/adapters/sourceRegistryAdapter";

const viewToNavItem: Record<DashboardView, SideNavItemId> = {
  world: "world-dashboard",
  sources: "sources",
  timeseries: "time-series"
};

const navItemToView: Record<SideNavItemId, DashboardView> = {
  "world-dashboard": "world",
  sources: "sources",
  "time-series": "timeseries"
};

export function DashboardShell() {
  const {
    view,
    setView,
    selectedCountry,
    setSelectedCountry,
    setHoverCountry,
    sources,
    addUserSource,
    uploadedDatasets,
    addUploadedDataset,
    activeTimeSeriesSourceId,
    setActiveTimeSeriesSourceId,
    activeMetric,
    setActiveMetric,
    activeDateRange,
    setActiveDateRange
  } = useDashboard();

  const coverageCounts = sources.reduce<Record<string, number>>((counts, source) => {
    source.supportedCountries.forEach((iso3) => {
      if (iso3 === "GLOBAL") return;
      counts[iso3] = (counts[iso3] ?? 0) + 1;
    });
    return counts;
  }, {});

  const selectedCountrySources = getSourcesForCountry(sources, selectedCountry?.iso3 ?? null);

  const content =
    view === "sources" ? (
      <SourcesPage selectedCountry={selectedCountry} sources={sources} onAddSource={addUserSource} />
    ) : view === "timeseries" ? (
      <TimeSeriesPage
        selectedCountry={selectedCountry}
        sources={selectedCountrySources}
        datasets={uploadedDatasets}
        activeSourceId={activeTimeSeriesSourceId}
        activeMetric={activeMetric}
        dateRange={activeDateRange}
        onSourceChange={(sourceId) => {
          setActiveTimeSeriesSourceId(sourceId || null);
          setActiveMetric(null);
        }}
        onMetricChange={(metric) => setActiveMetric(metric || null)}
        onDateRangeChange={setActiveDateRange}
        onDatasetReady={addUploadedDataset}
      />
    ) : (
      <div className="h-[calc(100vh-2rem)] min-h-[720px]">
        <WorldMap
          selectedCountry={selectedCountry}
          coverageCounts={coverageCounts}
          onCountrySelect={setSelectedCountry}
          onCountryHover={setHoverCountry}
        />
      </div>
    );

  return (
    <div className="min-h-screen bg-ink-950 text-white">
      <div className="grid min-h-screen lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="sticky top-0 z-30 border-b border-white/10 bg-black/95 p-4 backdrop-blur lg:h-screen lg:border-b-0 lg:border-r">
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase text-red-300">Sentinel Atlas</p>
            <h1 className="mt-1 text-xl font-semibold">Country Data Workspace</h1>
            <p className="mt-3 text-sm leading-6 text-neutral-400">
              Select countries on the map, inspect source coverage, and upload time-series records.
            </p>
          </div>
          <SideNav activeItem={viewToNavItem[view] ?? "world-dashboard"} onSelect={(item) => setView(navItemToView[item])} />

          <div className="mt-6 rounded-xl border border-white/10 bg-white/[0.04] p-4 text-sm text-neutral-300">
            <div className="flex items-center gap-2 text-neutral-100">
              <ShieldCheck className="h-4 w-4 text-red-400" aria-hidden="true" />
              <span className="font-semibold">Privacy boundary</span>
            </div>
            <p className="mt-2 leading-6">
              Uses source metadata and uploaded records without individual-level tracking, diagnosis, medical advice, or operational public alerts.
            </p>
          </div>

          {selectedCountry && (
            <div className="mt-4 rounded-xl border border-red-500/30 bg-red-950/20 p-4">
              <p className="text-xs font-semibold uppercase text-red-300">Selected</p>
              <p className="mt-1 text-lg font-semibold">{selectedCountry.name}</p>
              <p className="mt-1 font-mono text-xs text-neutral-400">{selectedCountry.iso3}</p>
            </div>
          )}
        </aside>

        <main className="p-4 lg:p-6">{content}</main>
      </div>
    </div>
  );
}
