import { describe, expect, it } from "vitest";
import { buildUserDataset, parseCsvText } from "./parser";

describe("parseCsvText", () => {
  it("parses a simple date+value CSV", () => {
    const text = "date,value\n2024-01-01,10\n2024-01-08,12\n";
    const { rows, fields, parseErrors } = parseCsvText(text);
    expect(parseErrors).toEqual([]);
    expect(fields).toEqual(["date", "value"]);
    expect(rows).toEqual([
      { date: "2024-01-01", value: 10 },
      { date: "2024-01-08", value: 12 }
    ]);
  });

  it("coerces numeric strings to numbers, leaves date strings alone", () => {
    const { rows } = parseCsvText("date,value\n2024-01-01,10.5\n");
    expect(typeof rows[0].value).toBe("number");
    expect(rows[0].value).toBe(10.5);
    expect(typeof rows[0].date).toBe("string");
  });

  it("treats empty cells as null", () => {
    const { rows } = parseCsvText("date,value\n2024-01-01,\n");
    expect(rows[0].value).toBeNull();
  });

  it("trims whitespace from headers and values", () => {
    const text = " date , value \n 2024-01-01 , 10 \n";
    const { fields, rows } = parseCsvText(text);
    expect(fields).toEqual(["date", "value"]);
    expect(rows[0]).toEqual({ date: "2024-01-01", value: 10 });
  });

  it("strips a leading BOM", () => {
    const { fields } = parseCsvText("﻿date,value\n2024-01-01,10\n");
    expect(fields).toEqual(["date", "value"]);
  });

  it("does not coerce bare alphanumerics to numbers", () => {
    const { rows } = parseCsvText("date,name\n2024-01-01,foo\n");
    expect(rows[0].name).toBe("foo");
  });
});

describe("buildUserDataset", () => {
  it("succeeds with a date column + numeric column (no quantile)", () => {
    const parsed = parseCsvText("date,value\n2024-01-01,10\n2024-01-08,12\n");
    const result = buildUserDataset(parsed, { filename: "p.csv" });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.dataset.dateField).toBe("date");
    expect(result.dataset.numericFields).toContain("value");
    expect(result.dataset.quantileField).toBeNull();
    expect(result.dataset.rowCount).toBe(2);
    expect(result.dataset.filename).toBe("p.csv");
    expect(result.dataset.id).toMatch(/^user-/);
  });

  it("recognizes target_date as the date column", () => {
    const parsed = parseCsvText("target_date,prediction\n2024-01-01,10\n");
    const result = buildUserDataset(parsed, { filename: "t.csv" });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.dataset.dateField).toBe("target_date");
  });

  it("detects the quantile column and excludes it from numericFields", () => {
    const parsed = parseCsvText(
      "date,quantile,value\n2024-01-01,0.5,10\n2024-01-01,0.025,5\n"
    );
    const result = buildUserDataset(parsed, { filename: "q.csv" });
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.dataset.quantileField).toBe("quantile");
    expect(result.dataset.numericFields).toEqual(["value"]);
  });

  it("treats null quantile cells as point estimates (not validation errors)", () => {
    const parsed = parseCsvText(
      "date,quantile,value\n2024-01-01,,10\n2024-01-01,0.5,10\n"
    );
    const result = buildUserDataset(parsed, { filename: "q.csv" });
    expect(result.ok).toBe(true);
  });

  it("rejects quantile values outside [0,1]", () => {
    const parsed = parseCsvText(
      "date,quantile,value\n2024-01-01,1.5,10\n2024-01-01,0.5,10\n"
    );
    const result = buildUserDataset(parsed, { filename: "q.csv" });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.join(" ")).toMatch(/quantile/i);
  });

  it("fails when there are no rows", () => {
    const parsed = parseCsvText("date,value\n");
    const result = buildUserDataset(parsed, { filename: "empty.csv" });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.join(" ")).toMatch(/no data rows/i);
  });

  it("fails when no date column is found", () => {
    const parsed = parseCsvText("foo,value\nbar,10\n");
    const result = buildUserDataset(parsed, { filename: "no-date.csv" });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.join(" ")).toMatch(/date column/i);
  });

  it("fails when no numeric column is found (quantile alone doesn't count)", () => {
    const parsed = parseCsvText("date,quantile\n2024-01-01,0.5\n");
    const result = buildUserDataset(parsed, { filename: "no-num.csv" });
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.errors.join(" ")).toMatch(/numeric/i);
  });
});
