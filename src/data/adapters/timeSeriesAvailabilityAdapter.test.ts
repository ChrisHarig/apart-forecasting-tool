import { describe, expect, it } from "vitest";
import {
  deriveAvailableTimeSeriesOptions,
  getLocalTimeSeriesAvailability,
  getTimeSeriesRecordsForSelection,
  normalizeBackendTimeSeriesRecord
} from "./timeSeriesAvailabilityAdapter";
import { normalizeUploadedTimeSeries } from "./timeSeriesUploadAdapter";
import type { TimeSeriesRecord, UploadedDataset } from "../../types/timeseries";

const records: TimeSeriesRecord[] = [
  {
    sourceId: "user-wastewater",
    countryIso3: "USA",
    date: "2026-04-01",
    metric: "normalized_signal",
    value: 10,
    unit: "index",
    provenance: "User upload"
  },
  {
    sourceId: "user-wastewater",
    countryIso3: "USA",
    date: "2026-04-10",
    metric: "normalized_signal",
    value: 12,
    unit: "index",
    provenance: "User upload"
  },
  {
    sourceId: "user-wastewater",
    countryIso3: "CAN",
    date: "2026-04-10",
    metric: "normalized_signal",
    value: 8,
    unit: "index",
    provenance: "User upload"
  },
  {
    sourceId: "user-lab",
    countryIso3: "USA",
    date: "2026-04-12",
    metric: "positivity_rate",
    value: 2.4,
    unit: "%",
    provenance: "User upload"
  }
];

const uploadedDatasets: UploadedDataset[] = [
  {
    id: "dataset-1",
    sourceId: "user-wastewater",
    sourceName: "Uploaded wastewater source",
    fileName: "signals.csv",
    records,
    uploadedAt: "2026-04-25T00:00:00.000Z",
    validationWarnings: []
  }
];

describe("time-series availability adapter", () => {
  it("derives available source and metric options from actual uploaded records", () => {
    const options = deriveAvailableTimeSeriesOptions(records, "USA", {
      "user-wastewater": "Uploaded wastewater source",
      "user-lab": "Uploaded lab source"
    });

    expect(options.map((option) => `${option.sourceId}:${option.metric}:${option.recordCount}`)).toEqual([
      "user-lab:positivity_rate:1",
      "user-wastewater:normalized_signal:2"
    ]);
  });

  it("filters records by selected country, source, metric, and date range", () => {
    const filtered = getTimeSeriesRecordsForSelection({
      countryIso3: "USA",
      sourceId: "user-wastewater",
      metric: "normalized_signal",
      dateRange: { preset: "14d" },
      records
    });

    expect(filtered.map((record) => `${record.countryIso3}:${record.date}:${record.value}`)).toEqual([
      "USA:2026-04-01:10",
      "USA:2026-04-10:12"
    ]);
  });

  it("does not return records from another country for USA", () => {
    const filtered = getTimeSeriesRecordsForSelection({
      countryIso3: "USA",
      records
    });

    expect(filtered.every((record) => record.countryIso3 === "USA")).toBe(true);
    expect(filtered.map((record) => record.countryIso3)).not.toContain("CAN");
  });

  it("returns a clean empty availability result when no real records exist", () => {
    expect(getLocalTimeSeriesAvailability("USA", [])).toEqual({
      countryIso3: "USA",
      options: [],
      records: [],
      status: "empty"
    });
  });

  it("normalizes future backend camelCase and snake_case record shapes", () => {
    expect(
      normalizeBackendTimeSeriesRecord({
        country_iso3: "usa",
        source_id: "backend-source",
        observed_at: "2026-04-12T12:00:00Z",
        signal_category: "reported_count",
        value: "42",
        provenance_url: "https://example.test/provenance"
      })
    ).toMatchObject({
      countryIso3: "USA",
      sourceId: "backend-source",
      date: "2026-04-12",
      metric: "reported_count",
      value: 42,
      provenance: "https://example.test/provenance"
    });
  });

  it("keeps PII-like upload fields rejected", () => {
    const result = normalizeUploadedTimeSeries(
      "date,metric,value,countryIso3,patient_id\n2026-04-01,signal,10,USA,p-1",
      "bad.csv",
      "user-wastewater"
    );

    expect(result.records).toEqual([]);
    expect(result.errors.join(" ")).toMatch(/individual|medical-record|patient_id/i);
  });

  it("can build local availability from uploaded datasets", () => {
    const result = getLocalTimeSeriesAvailability("USA", uploadedDatasets);

    expect(result.status).toBe("local");
    expect(result.records).toHaveLength(3);
    expect(result.options).toHaveLength(2);
  });
});
