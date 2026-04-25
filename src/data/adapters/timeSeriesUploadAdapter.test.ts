import { describe, expect, it } from "vitest";
import { normalizeUploadedTimeSeries } from "./timeSeriesUploadAdapter";

describe("time-series upload adapter", () => {
  it("normalizes valid CSV uploads to country-scoped aggregate records", () => {
    const result = normalizeUploadedTimeSeries(
      [
        "date,value,metric,country,unit,provenance",
        "2026-04-01,12.5,wastewater_index,United States,index,Analyst upload"
      ].join("\n"),
      "wastewater.csv",
      "user-source"
    );

    expect(result.errors).toEqual([]);
    expect(result.records).toEqual([
      {
        sourceId: "user-source",
        countryIso3: "USA",
        date: "2026-04-01",
        metric: "wastewater_index",
        value: 12.5,
        unit: "index",
        provenance: "Analyst upload"
      }
    ]);
  });

  it("normalizes valid JSON array uploads", () => {
    const result = normalizeUploadedTimeSeries(
      JSON.stringify([{ date: "2026/04/02", value: "7", metric: "clinic_visits", countryIso3: "CAN" }]),
      "clinical.json",
      "user-source"
    );

    expect(result.errors).toEqual([]);
    expect(result.records[0]).toMatchObject({
      countryIso3: "CAN",
      date: "2026-04-02",
      metric: "clinic_visits",
      value: 7
    });
  });

  it("reports validation errors instead of filling missing values", () => {
    const result = normalizeUploadedTimeSeries("date,value,metric,country\n2026-04-01,,cases,USA", "invalid.csv", "user-source");

    expect(result.records).toEqual([]);
    expect(result.errors.join(" ")).toMatch(/value/i);
  });

  it("rejects likely PII, medical-record, or precise personal trace fields", () => {
    const result = normalizeUploadedTimeSeries(
      "date,value,metric,country,patient_id\n2026-04-01,2,cases,USA,abc-123",
      "pii.csv",
      "user-source"
    );

    expect(result.records).toEqual([]);
    expect(result.errors.join(" ")).toMatch(/individual|medical-record|trace/i);
  });
});
