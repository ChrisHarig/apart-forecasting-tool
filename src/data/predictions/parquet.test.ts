import { describe, expect, it } from "vitest";
import { parquetReadObjects } from "hyparquet";
import { parquetMetadata } from "hyparquet";
import { serializePredictionParquet } from "./parquet";
import type { UserDataset } from "./types";

function makeDataset(): UserDataset {
  return {
    id: "test-1",
    filename: "demo.csv",
    uploadedAt: 1_700_000_000_000,
    dateField: "date",
    quantileField: "quantile",
    numericFields: ["value"],
    rowCount: 4,
    rows: [
      { date: "2025-01-01", quantile: null, value: 100, location: "CA" },
      { date: "2025-01-01", quantile: 0.5, value: 105, location: "CA" },
      { date: "2025-01-01", quantile: 0.9, value: 130, location: "CA" },
      { date: "2025-01-08", quantile: null, value: 110, location: "CA" }
    ]
  };
}

describe("serializePredictionParquet", () => {
  it("produces a parquet whose rows roundtrip with the expected columns", async () => {
    const ds = makeDataset();
    const out = serializePredictionParquet(ds, {
      submitter: "Alice",
      modelName: "MyModel v0.1",
      description: "test submission",
      targetDataset: "nhsn-hrd",
      targetColumn: "totalconfflunewadm",
      passthroughDims: ["location"],
      submittedAt: new Date("2026-04-26T12:34:56Z")
    });

    expect(out.rowCount).toBe(4);
    expect(out.filename).toMatch(/^data\/alice-mymodel-v0-1-\d{14}\.parquet$/);

    const rows = await parquetReadObjects({
      file: out.buffer
    });
    expect(rows).toHaveLength(4);
    const r0 = rows[0] as Record<string, unknown>;
    expect(r0.target_date).toBe("2025-01-01");
    expect(r0.target_dataset).toBe("nhsn-hrd");
    expect(r0.target_column).toBe("totalconfflunewadm");
    expect(r0.submitter).toBe("Alice");
    expect(r0.model_name).toBe("MyModel v0.1");
    expect(r0.value).toBe(100);
    expect(r0.quantile).toBeNull();
    expect(r0.location).toBe("CA");

    const r1 = rows[1] as Record<string, unknown>;
    expect(r1.quantile).toBeCloseTo(0.5, 6);
    const r2 = rows[2] as Record<string, unknown>;
    expect(r2.quantile).toBeCloseTo(0.9, 6);
  });

  it("embeds schema-version metadata in the file footer", async () => {
    const ds = makeDataset();
    const out = serializePredictionParquet(ds, {
      submitter: "bob",
      modelName: "x",
      description: "",
      targetDataset: "nhsn-hrd",
      targetColumn: "totalconfflunewadm"
    });
    const meta = await parquetMetadata(out.buffer);
    const kvs = (meta.key_value_metadata ?? []).reduce<Record<string, string>>(
      (acc, kv) => ((acc[kv.key] = kv.value ?? ""), acc),
      {}
    );
    expect(kvs["epi-eval.schema_version"]).toBe("1");
    expect(kvs["epi-eval.target_dataset"]).toBe("nhsn-hrd");
    expect(kvs["epi-eval.target_column"]).toBe("totalconfflunewadm");
    expect(kvs["epi-eval.submitter"]).toBe("bob");
  });

  it("rejects datasets with no value column", () => {
    const ds = makeDataset();
    const broken: UserDataset = { ...ds, numericFields: [] };
    expect(() =>
      serializePredictionParquet(broken, {
        submitter: "x",
        modelName: "y",
        description: "",
        targetDataset: "nhsn-hrd",
        targetColumn: "totalconfflunewadm"
      })
    ).toThrow(/no value column/i);
  });

  it("skips rows with unparseable dates or non-numeric values", () => {
    const ds: UserDataset = {
      ...makeDataset(),
      rows: [
        { date: "2025-01-01", quantile: null, value: 50 },
        { date: "not-a-date", quantile: null, value: 60 },
        { date: "2025-01-08", quantile: null, value: "oops" }
      ]
    };
    const out = serializePredictionParquet(ds, {
      submitter: "x",
      modelName: "y",
      description: "",
      targetDataset: "nhsn-hrd",
      targetColumn: "totalconfflunewadm"
    });
    expect(out.rowCount).toBe(1);
  });
});
