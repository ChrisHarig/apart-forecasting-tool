import { useState, type ChangeEvent } from "react";
import type { DataSourceMetadata } from "../../types/source";
import type { UploadedDataset } from "../../types/timeseries";
import { normalizeUploadedTimeSeries, timeSeriesUploadAdapter } from "../../data/adapters/timeSeriesUploadAdapter";

interface UploadDatasetPanelProps {
  selectedSource: DataSourceMetadata | null;
  uploadSources: DataSourceMetadata[];
  onSourceChange: (sourceId: string) => void;
  onDatasetReady: (dataset: UploadedDataset) => void;
}

export function UploadDatasetPanel({ selectedSource, uploadSources, onSourceChange, onDatasetReady }: UploadDatasetPanelProps) {
  const [messages, setMessages] = useState<string[]>([]);

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !selectedSource) return;

    if (!file.name.toLowerCase().endsWith(".csv") && !file.name.toLowerCase().endsWith(".json")) {
      setMessages(["Only CSV and JSON files are supported for aggregate time-series uploads."]);
      return;
    }

    const text = await file.text();
    const normalized = normalizeUploadedTimeSeries(text, file.name, selectedSource.id);
    if (normalized.errors.length > 0) {
      setMessages(normalized.errors);
      return;
    }

    const dataset = timeSeriesUploadAdapter.createDataset(file.name, selectedSource.id, selectedSource.name, normalized.records, normalized.warnings);
    onDatasetReady(dataset);
    setMessages([`Loaded ${dataset.records.length} aggregate records from ${file.name}.`]);
  };

  return (
    <div className="rounded-xl border border-white/10 bg-black p-4 text-white">
      <p className="text-xs font-semibold uppercase text-red-300">Upload aggregate time series</p>
      <p className="mt-2 text-sm leading-6 text-neutral-400">
        Accepted schema: date, value, metric, and countryIso3 or country name. Optional fields include unit, locationName, latitude, longitude, admin fields, provenance, and notes.
      </p>
      {uploadSources.length > 0 && (
        <label className="mt-4 grid gap-2 text-xs font-semibold uppercase text-neutral-500">
          Upload target
          <select
            className="rounded-md border border-white/10 bg-neutral-950 px-3 py-2 text-sm font-normal text-white"
            value={selectedSource?.id ?? ""}
            onChange={(event) => onSourceChange(event.target.value)}
          >
            {!selectedSource && <option value="">Select upload source</option>}
            {uploadSources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </label>
      )}
      <input
        className="mt-4 block w-full rounded-md border border-white/10 bg-neutral-950 px-3 py-2 text-sm"
        type="file"
        accept=".csv,.json,application/json,text/csv"
        disabled={!selectedSource}
        onChange={handleFile}
      />
      {!selectedSource && <p className="mt-2 text-xs text-neutral-500">Add a user-upload source before uploading data.</p>}
      {messages.length > 0 && (
        <div className="mt-3 space-y-1 text-sm">
          {messages.map((message) => (
            <p key={message} className="rounded-md border border-white/10 bg-white/[0.04] p-2 text-neutral-200">
              {message}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
