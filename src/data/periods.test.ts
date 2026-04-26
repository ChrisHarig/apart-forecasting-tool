import { describe, expect, it } from "vitest";
import {
  BUILTIN_PERIOD_KINDS,
  dateToPeriod,
  formatPeriodTick,
  periodKindLabel,
  periodLengthDays,
  sortPeriodIdsNewestFirst
} from "./periods";

const utc = (y: number, m: number, d: number) => new Date(Date.UTC(y, m - 1, d));

describe("dateToPeriod — calendar-year", () => {
  const kind = { kind: "calendar-year" } as const;

  it("Jan 1 → xIndex 0", () => {
    const a = dateToPeriod(utc(2023, 1, 1), kind);
    expect(a.periodId).toBe("2023");
    expect(a.xIndex).toBe(0);
  });

  it("Dec 31 of a non-leap year → xIndex 364", () => {
    const a = dateToPeriod(utc(2023, 12, 31), kind);
    expect(a.xIndex).toBe(364);
  });

  it("Dec 31 of a leap year → xIndex 365", () => {
    const a = dateToPeriod(utc(2020, 12, 31), kind);
    expect(a.xIndex).toBe(365);
  });

  it("crossing the year boundary changes the periodId", () => {
    expect(dateToPeriod(utc(2022, 12, 31), kind).periodId).toBe("2022");
    expect(dateToPeriod(utc(2023, 1, 1), kind).periodId).toBe("2023");
  });
});

describe("dateToPeriod — flu-season northern", () => {
  const kind = { kind: "flu-season", hemisphere: "northern" } as const;

  it("Oct 1 starts a new season at xIndex 0", () => {
    const a = dateToPeriod(utc(2023, 10, 1), kind);
    expect(a.periodId).toBe("2023-24");
    expect(a.xIndex).toBe(0);
  });

  it("Sep 30 closes the prior season at large xIndex", () => {
    const a = dateToPeriod(utc(2023, 9, 30), kind);
    expect(a.periodId).toBe("2022-23");
    // From Oct 1 2022 to Sep 30 2023 is 364 days (non-leap-spanning year).
    expect(a.xIndex).toBe(364);
  });

  it("Jan 1 belongs to the season that started the previous October", () => {
    const a = dateToPeriod(utc(2024, 1, 1), kind);
    expect(a.periodId).toBe("2023-24");
    // Oct 1 2023 + 92 days = Jan 1 2024.
    expect(a.xIndex).toBe(92);
  });

  it("season periodId formats as YYYY-YY (zero-padded short next year)", () => {
    expect(dateToPeriod(utc(1999, 11, 1), kind).periodId).toBe("1999-00");
    expect(dateToPeriod(utc(2009, 11, 1), kind).periodId).toBe("2009-10");
  });
});

describe("dateToPeriod — flu-season southern", () => {
  const kind = { kind: "flu-season", hemisphere: "southern" } as const;

  it("Apr 1 starts a new season at xIndex 0", () => {
    const a = dateToPeriod(utc(2023, 4, 1), kind);
    expect(a.periodId).toBe("2023-24");
    expect(a.xIndex).toBe(0);
  });

  it("Mar 31 closes the prior season", () => {
    const a = dateToPeriod(utc(2023, 3, 31), kind);
    expect(a.periodId).toBe("2022-23");
  });
});

describe("dateToPeriod — calendar-month", () => {
  const kind = { kind: "calendar-month" } as const;

  it("each month is its own period", () => {
    const a = dateToPeriod(utc(2023, 10, 15), kind);
    expect(a.periodId).toBe("2023-10");
    expect(a.xIndex).toBe(14);
  });

  it("month boundary changes the periodId", () => {
    expect(dateToPeriod(utc(2023, 1, 31), kind).periodId).toBe("2023-01");
    expect(dateToPeriod(utc(2023, 2, 1), kind).periodId).toBe("2023-02");
  });
});

describe("periodLengthDays", () => {
  it("returns 366 for year-shaped periods (leap-year tolerance)", () => {
    expect(periodLengthDays({ kind: "calendar-year" })).toBe(366);
    expect(periodLengthDays({ kind: "flu-season", hemisphere: "northern" })).toBe(366);
  });

  it("returns 31 for calendar-month", () => {
    expect(periodLengthDays({ kind: "calendar-month" })).toBe(31);
  });
});

describe("formatPeriodTick", () => {
  it("renders calendar-year x=0 as Jan", () => {
    const label = formatPeriodTick(0, { kind: "calendar-year" });
    // Locale-dependent but always contains "Jan" / "1".
    expect(label).toMatch(/Jan|1\b/);
  });

  it("renders flu-season-northern x=0 as Oct", () => {
    const label = formatPeriodTick(0, { kind: "flu-season", hemisphere: "northern" });
    expect(label).toMatch(/Oct/);
  });

  it("renders flu-season-northern x=92 as Jan 1 of the following year", () => {
    const label = formatPeriodTick(92, { kind: "flu-season", hemisphere: "northern" });
    // 92 days after Oct 1 2023 = Jan 1 2024 (non-leap year reference).
    expect(label).toMatch(/Jan/);
  });
});

describe("sortPeriodIdsNewestFirst", () => {
  it("orders calendar-year ids newest first", () => {
    expect(sortPeriodIdsNewestFirst(["2020", "2023", "2021", "2022"])).toEqual([
      "2023",
      "2022",
      "2021",
      "2020"
    ]);
  });

  it("orders flu-season ids newest first by start year", () => {
    expect(sortPeriodIdsNewestFirst(["2020-21", "2023-24", "2021-22", "2022-23"])).toEqual([
      "2023-24",
      "2022-23",
      "2021-22",
      "2020-21"
    ]);
  });

  it("does not mutate the input", () => {
    const input = ["2020", "2023", "2021"];
    const out = sortPeriodIdsNewestFirst(input);
    expect(input).toEqual(["2020", "2023", "2021"]);
    expect(out).not.toBe(input);
  });
});

describe("BUILTIN_PERIOD_KINDS + periodKindLabel", () => {
  it("offers calendar-year, both flu-season hemispheres, and calendar-month", () => {
    const labels = BUILTIN_PERIOD_KINDS.map(periodKindLabel);
    expect(labels).toContain("Calendar year");
    expect(labels).toContain("Flu season (northern)");
    expect(labels).toContain("Flu season (southern)");
    expect(labels).toContain("Calendar month");
    // Fiscal year removed — wasn't a useful default for this dataset mix.
    expect(labels.some((l) => l.startsWith("Fiscal year"))).toBe(false);
  });
});
