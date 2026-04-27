import { describe, expect, it } from "vitest";
import { companionRepoId, parsePredictionRows } from "./companion";

describe("companionRepoId", () => {
  it("forms the EPI-Eval/<id>-predictions slug", () => {
    expect(companionRepoId("nhsn-hrd")).toBe("EPI-Eval/nhsn-hrd-predictions");
    expect(companionRepoId("flusight-forecast-hub")).toBe(
      "EPI-Eval/flusight-forecast-hub-predictions"
    );
  });
});

describe("parsePredictionRows", () => {
  it("groups by submitter, separates point estimates from quantiles, and pulls dims", () => {
    const parsed = parsePredictionRows([
      // alice — 1 date, point + 0.5 quantile
      {
        target_date: "2026-01-01",
        target_dataset: "nhsn-hrd",
        target_column: "totalconfflunewadm",
        submitter: "alice",
        model_name: "v1",
        description: "test",
        quantile: null,
        value: 100,
        location: "CA"
      },
      {
        target_date: "2026-01-01",
        target_dataset: "nhsn-hrd",
        target_column: "totalconfflunewadm",
        submitter: "alice",
        model_name: "v1",
        description: "test",
        quantile: 0.5,
        value: 100,
        location: "CA"
      },
      // team-baseline — synthetic naming
      {
        target_date: "2026-01-08",
        target_dataset: "nhsn-hrd",
        target_column: "totalconfflunewadm",
        submitter: "team-baseline",
        model_name: "naive",
        description: "synth",
        quantile: null,
        value: 110,
        location: "CA"
      }
    ]);

    expect(parsed.rows).toHaveLength(3);
    expect(parsed.submitters.map((s) => s.submitter)).toEqual(["alice", "team-baseline"]);
    expect(parsed.dimNames).toEqual(["location"]);
    expect(parsed.dateRange).toEqual({ min: "2026-01-01", max: "2026-01-08" });

    const alice = parsed.submitters.find((s) => s.submitter === "alice")!;
    expect(alice.rowCount).toBe(2);
    expect(alice.pointDateCount).toBe(1);
    expect(alice.isSynthetic).toBe(false);

    const synth = parsed.submitters.find((s) => s.submitter === "team-baseline")!;
    expect(synth.isSynthetic).toBe(true);

    const aliceRows = parsed.rowsBySubmitter.get("alice")!;
    expect(aliceRows.find((r) => r.quantile === null)?.value).toBe(100);
    expect(aliceRows.find((r) => r.quantile === 0.5)?.value).toBe(100);
    expect(aliceRows[0].dims.location).toBe("CA");
  });

  it("drops malformed rows (no date, no submitter, non-numeric value, out-of-range quantile)", () => {
    const parsed = parsePredictionRows([
      // missing target_date
      { submitter: "x", value: 1, quantile: null },
      // missing submitter
      { target_date: "2026-01-01", value: 1, quantile: null },
      // non-numeric value
      { target_date: "2026-01-01", submitter: "x", value: "oops", quantile: null },
      // quantile out of [0,1] — row kept but quantile coerced to null
      {
        target_date: "2026-01-01",
        submitter: "x",
        model_name: "y",
        value: 5,
        quantile: 1.5
      },
      // valid
      {
        target_date: "2026-01-02",
        submitter: "y",
        model_name: "y",
        value: 5,
        quantile: 0.5
      }
    ]);
    expect(parsed.rows).toHaveLength(2);
    const xRow = parsed.rows.find((r) => r.submitter === "x")!;
    expect(xRow.quantile).toBeNull();
  });

  it("handles an empty input cleanly", () => {
    const parsed = parsePredictionRows([]);
    expect(parsed.rows).toHaveLength(0);
    expect(parsed.submitters).toHaveLength(0);
    expect(parsed.dateRange).toBeNull();
  });
});
