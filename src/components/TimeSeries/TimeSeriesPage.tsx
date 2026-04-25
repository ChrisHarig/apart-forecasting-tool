import { useEffect, useMemo } from "react";
import type { SelectedCountry } from "../../types/dashboard";
import type { DataSourceMetadata } from "../../types/source";
import type { DateRangeState, UploadedDataset } from "../../types/timeseries";
import {
  getLocalTimeSeriesAvailability,
  getTimeSeriesRecordsForSelection
} from "../../data/adapters/timeSeriesAvailabilityAdapter";
import { Panel } from "../ui/Panel";
import { EmptyState } from "../ui/EmptyState";
import { TimeSeriesChart } from "./TimeSeriesChart";
import { TimeSeriesControls } from "./TimeSeriesControls";
import { UploadDatasetPanel } from "./UploadDatasetPanel";

interface TimeSeriesPageProps {
  selectedCountry: SelectedCountry | null;
  sources: DataSourceMetadata[];
  datasets: UploadedDataset[];
  activeSourceId: string | null;
  activeMetric: string | null;
  dateRange: DateRangeState;
  onSourceChange: (sourceId: string) => void;
  onMetricChange: (metric: string) => void;
  onDateRangeChange: (range: DateRangeState) => void;
  onDatasetReady: (dataset: UploadedDataset) => void;
}

export function TimeSeriesPage({
  selectedCountry,
  sources,
  datasets,
  activeSourceId,
  activeMetric,
  dateRange,
  onSourceChange,
  onMetricChange,
  onDateRangeChange,
  onDatasetReady
}: TimeSeriesPageProps) {
  const countryIso3 = selectedCountry?.iso3 ?? "";
  const availability = useMemo(
    () =>
      selectedCountry
        ? getLocalTimeSeriesAvailability(selectedCountry.iso3, datasets)
        : { countryIso3: "", options: [], records: [], status: "empty" as const },
    [datasets, selectedCountry]
  );
  const uploadSources = useMemo(
    () => sources.filter((source) => source.userAdded || source.accessType === "user_upload"),
    [sources]
  );
  const effectiveOption = useMemo(() => {
    if (availability.options.length === 0) return null;
    return (
      availability.options.find((option) => option.sourceId === activeSourceId && option.metric === activeMetric) ??
      availability.options.find((option) => option.sourceId === activeSourceId) ??
      availability.options[0]
    );
  }, [activeMetric, activeSourceId, availability.options]);
  const effectiveSourceId = effectiveOption?.sourceId ?? activeSourceId;
  const effectiveMetric = effectiveOption?.metric ?? activeMetric;
  const uploadTargetSource = uploadSources.find((source) => source.id === activeSourceId) ?? uploadSources[0] ?? null;
  const filteredRecords =
    selectedCountry && effectiveOption
      ? getTimeSeriesRecordsForSelection({
          countryIso3,
          sourceId: effectiveOption.sourceId,
          metric: effectiveOption.metric,
          dateRange,
          records: availability.records
        })
      : [];

  useEffect(() => {
    if (!effectiveOption) return;
    if (activeSourceId !== effectiveOption.sourceId) {
      onSourceChange(effectiveOption.sourceId);
    }
    if (activeMetric !== effectiveOption.metric) {
      onMetricChange(effectiveOption.metric);
    }
  }, [activeMetric, activeSourceId, effectiveOption, onMetricChange, onSourceChange]);

  if (!selectedCountry) {
    return (
      <Panel eyebrow="Time Series" title="Select a country first">
        <EmptyState title="Select a country on the world map first." body="Time-series records are filtered by selected country and source provenance." />
      </Panel>
    );
  }

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-white/10 bg-black p-5 text-white">
        <p className="text-xs font-semibold uppercase text-red-300">Time Series</p>
        <h1 className="mt-1 text-3xl font-semibold">{selectedCountry.name}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-400">
          This section renders only uploaded or adapter-provided aggregate records. The frontend does not generate values.
        </p>
      </div>

      <TimeSeriesControls
        selectedCountryName={selectedCountry.name}
        availableOptions={availability.options}
        sourceId={effectiveSourceId ?? null}
        metric={effectiveMetric ?? null}
        dateRange={dateRange}
        onSourceChange={onSourceChange}
        onMetricChange={onMetricChange}
        onDateRangeChange={onDateRangeChange}
      />

      {availability.options.length > 0 && effectiveOption && (
        <div className="grid gap-3 rounded-xl border border-white/10 bg-white/[0.04] p-4 text-sm text-neutral-300 md:grid-cols-4">
          <div>
            <p className="text-xs font-semibold uppercase text-neutral-500">Source</p>
            <p className="mt-1 text-white">{effectiveOption.sourceName}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-neutral-500">Metric</p>
            <p className="mt-1 text-white">{effectiveOption.metric}</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-neutral-500">Records</p>
            <p className="mt-1 text-white">{filteredRecords.length.toLocaleString()} shown</p>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase text-neutral-500">Provenance</p>
            <p className="mt-1 text-white">{effectiveOption.statusNote}</p>
          </div>
        </div>
      )}

      <UploadDatasetPanel
        selectedSource={uploadTargetSource}
        uploadSources={uploadSources}
        onSourceChange={onSourceChange}
        onDatasetReady={onDatasetReady}
      />

      {filteredRecords.length > 0 ? (
        <div className="space-y-4">
          <TimeSeriesChart records={filteredRecords} />
          <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white text-black">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-neutral-100 text-xs uppercase text-neutral-600">
                <tr>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Metric</th>
                  <th className="px-3 py-2">Value</th>
                  <th className="px-3 py-2">Unit</th>
                  <th className="px-3 py-2">Provenance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-200">
                {filteredRecords.slice(0, 50).map((record, index) => (
                  <tr key={`${record.sourceId}-${record.date}-${record.metric}-${index}`}>
                    <td className="px-3 py-2">{record.date}</td>
                    <td className="px-3 py-2">{record.metric}</td>
                    <td className="px-3 py-2">{record.value}</td>
                    <td className="px-3 py-2">{record.unit || "-"}</td>
                    <td className="px-3 py-2">{record.provenance || "User upload"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <Panel>
          <EmptyState title="No time-series data for this country/source yet" body="Add a source and upload aggregate CSV or JSON records to render a chart." />
        </Panel>
      )}
    </div>
  );
}
