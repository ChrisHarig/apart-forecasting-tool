import { describe, expect, it } from "vitest";
import { detectDateField, detectNumericFields } from "./rows";

describe("detectDateField", () => {
  it("prefers an exact 'date' column", () => {
    expect(detectDateField([{ date: "2026-04-25", value: 1 }])).toBe("date");
  });
  it("falls back to anything containing 'date'", () => {
    expect(detectDateField([{ report_date: "2026-04-25", value: 1 }])).toBe("report_date");
  });
  it("returns null when nothing date-like is present", () => {
    expect(detectDateField([{ x: 1, y: 2 }])).toBeNull();
  });
});

describe("detectNumericFields", () => {
  it("returns columns whose samples are mostly numeric", () => {
    const rows = [
      { date: "2026-04-25", count: 5, label: "a" },
      { date: "2026-04-26", count: 7, label: "b" }
    ];
    expect(detectNumericFields(rows, ["date"])).toEqual(["count"]);
  });
  it("treats numeric strings as numeric", () => {
    const rows = [{ rate: "1.5" }, { rate: "2.0" }];
    expect(detectNumericFields(rows)).toEqual(["rate"]);
  });
});
