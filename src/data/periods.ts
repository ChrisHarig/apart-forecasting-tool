// Period helpers for the seasonal / year-over-year chart mode.
//
// A "period" is a recurring time interval (calendar year, flu season N/S,
// calendar month). Mapping a date to a period gives us a (periodId, xIndex)
// pair: the line the date contributes to and its position-within-period on
// the shared X axis.
//
// All math runs in UTC so daylight-saving and timezone shifts don't move
// dates between periods. The dashboard ingests epi data with date in UTC
// throughout (period-end Saturday/Sunday), which fits this assumption.

export type PeriodKind =
  | { kind: "calendar-year" }
  | { kind: "flu-season"; hemisphere: "northern" | "southern" }
  | { kind: "calendar-month" };

export interface PeriodAssignment {
  /** Stable identifier for the period — used as the chart series key. */
  periodId: string;
  /** Day-of-period (0 = first day of the period). */
  xIndex: number;
  /** Calendar date at xIndex=0; used for tick labels. */
  periodStartDate: Date;
}

const MS_PER_DAY = 86_400_000;

function daysBetween(later: Date, earlier: Date): number {
  return Math.floor((later.getTime() - earlier.getTime()) / MS_PER_DAY);
}

function utcDate(year: number, month0: number, day: number): Date {
  return new Date(Date.UTC(year, month0, day));
}

/**
 * Map a calendar date to a (periodId, xIndex) pair under the given period
 * kind. Both periodId and xIndex are stable across re-runs given the same
 * input — no clock dependence.
 *
 * Edge cases:
 *   - calendar-year: Jan 1 = xIndex 0; Dec 31 of a non-leap year = 364.
 *   - flu-season-northern: Oct 1 = xIndex 0 of season `<year>-<year+1>`;
 *     Sep 30 closes the previous season at xIndex ~365.
 *   - flu-season-southern: Apr 1 = xIndex 0 of season starting that year.
 *   - calendar-month: each month is its own period (12+ lines per year).
 */
export function dateToPeriod(date: Date, kind: PeriodKind): PeriodAssignment {
  switch (kind.kind) {
    case "calendar-year": {
      const y = date.getUTCFullYear();
      const periodStart = utcDate(y, 0, 1);
      return {
        periodId: String(y),
        xIndex: daysBetween(date, periodStart),
        periodStartDate: periodStart
      };
    }
    case "flu-season": {
      // Northern: Oct 1 (month index 9) of year N → Sep 30 of N+1.
      // Southern: Apr 1 (month index 3) of year N → Mar 31 of N+1.
      const startMonth = kind.hemisphere === "northern" ? 9 : 3;
      const y = date.getUTCFullYear();
      const m = date.getUTCMonth();
      const seasonStartYear = m >= startMonth ? y : y - 1;
      const periodStart = utcDate(seasonStartYear, startMonth, 1);
      const seasonEndShortYear = (seasonStartYear + 1) % 100;
      return {
        periodId: `${seasonStartYear}-${String(seasonEndShortYear).padStart(2, "0")}`,
        xIndex: daysBetween(date, periodStart),
        periodStartDate: periodStart
      };
    }
    case "calendar-month": {
      const y = date.getUTCFullYear();
      const m = date.getUTCMonth();
      const periodStart = utcDate(y, m, 1);
      return {
        periodId: `${y}-${String(m + 1).padStart(2, "0")}`,
        xIndex: daysBetween(date, periodStart),
        periodStartDate: periodStart
      };
    }
  }
}

/**
 * Given a period kind, compute the maximum xIndex any period of that kind
 * will produce. Used for x-axis domain sizing.
 */
export function periodLengthDays(kind: PeriodKind): number {
  switch (kind.kind) {
    case "calendar-year":
      return 366; // 365 + leap-year tolerance
    case "flu-season":
      return 366; // Oct 1 → Sep 30 (leap-year tolerance)
    case "calendar-month":
      return 31;
  }
}

/**
 * Render a calendar-style label for an x-position within a period.
 * Used as the X-axis tick formatter — maps "day 47 of flu season" → "Nov 17".
 */
export function formatPeriodTick(xIndex: number, kind: PeriodKind, referenceStart?: Date): string {
  // Use the reference period start if given; otherwise pick a non-leap-year
  // representative so labels are deterministic regardless of which period
  // a row happens to come from.
  const refStart = referenceStart ?? defaultReferenceStart(kind);
  const d = new Date(refStart.getTime() + xIndex * MS_PER_DAY);
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    timeZone: "UTC"
  });
}

function defaultReferenceStart(kind: PeriodKind): Date {
  // 2023 is a non-leap year — predictable reference for tick rendering.
  switch (kind.kind) {
    case "calendar-year":
      return utcDate(2023, 0, 1);
    case "flu-season":
      return utcDate(2023, kind.hemisphere === "northern" ? 9 : 3, 1);
    case "calendar-month":
      return utcDate(2023, 0, 1);
  }
}

/** Stable display label for a period kind — used in selectors. */
export function periodKindLabel(kind: PeriodKind): string {
  switch (kind.kind) {
    case "calendar-year":
      return "Calendar year";
    case "flu-season":
      return `Flu season (${kind.hemisphere})`;
    case "calendar-month":
      return "Calendar month";
  }
}

/** Built-in period kinds the UI offers. Custom kinds are a v2 follow-up. */
export const BUILTIN_PERIOD_KINDS: PeriodKind[] = [
  { kind: "calendar-year" },
  { kind: "flu-season", hemisphere: "northern" },
  { kind: "flu-season", hemisphere: "southern" },
  { kind: "calendar-month" }
];

/**
 * Sort period IDs newest-first. Used to color and order series in the chart
 * (current period gets full saturation; older fade out).
 */
export function sortPeriodIdsNewestFirst(ids: string[]): string[] {
  // For all our kinds, the periodId starts with a 4-digit year (calendar-year
  // → "2023", flu-season → "2023-24", calendar-month → "2023-10").
  // Lex-descending on the prefix gives newest first.
  return [...ids].sort((a, b) => b.localeCompare(a));
}
