import type {
  AggregateTimeSeriesDateRange,
  AggregateTimeSeriesDateRangeSelection,
  AggregateTimeSeriesRecord,
  DateRangePreset,
  DateRangeState,
  TimeSeriesRecord
} from "../types/timeseries";

const DAY_MS = 24 * 60 * 60 * 1000;

const presetDays: Record<Exclude<DateRangePreset, "custom">, number> = {
  "14d": 14,
  "1m": 31,
  "3m": 92,
  "6m": 184,
  "1y": 366,
  "2y": 732
};

export function getDateRangeBounds(records: TimeSeriesRecord[], range: DateRangeState): { start?: string; end?: string } {
  if (range.preset === "custom") {
    return { start: range.customStart, end: range.customEnd };
  }

  const maxDate = records.reduce<string | undefined>((latest, record) => {
    if (!latest || record.date > latest) return record.date;
    return latest;
  }, undefined);

  if (!maxDate) return {};
  const end = new Date(`${maxDate}T00:00:00.000Z`);
  const start = new Date(end.getTime() - presetDays[range.preset] * DAY_MS);
  return { start: start.toISOString().slice(0, 10), end: maxDate };
}

export function filterRecordsByDateRange(records: TimeSeriesRecord[], range: DateRangeState): TimeSeriesRecord[] {
  const { start, end } = getDateRangeBounds(records, range);
  return records.filter((record) => (!start || record.date >= start) && (!end || record.date <= end));
}

const ISO_DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const YEAR_FIRST_DATE_PATTERN = /^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$/;
const MONTH_FIRST_DATE_PATTERN = /^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$/;

function padDatePart(value: number): string {
  return value.toString().padStart(2, "0");
}

function buildIsoDate(year: number, month: number, day: number): string | null {
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    return null;
  }

  const candidate = new Date(Date.UTC(year, month - 1, day));
  if (
    candidate.getUTCFullYear() !== year ||
    candidate.getUTCMonth() !== month - 1 ||
    candidate.getUTCDate() !== day
  ) {
    return null;
  }

  return `${year}-${padDatePart(month)}-${padDatePart(day)}`;
}

export function isIsoDate(value: string): boolean {
  if (!ISO_DATE_PATTERN.test(value)) {
    return false;
  }

  const [year, month, day] = value.split("-").map(Number);
  return buildIsoDate(year, month, day) === value;
}

export function normalizeDateInput(input: unknown): string | null {
  if (input === null || input === undefined) {
    return null;
  }

  const value = String(input).trim();
  if (!value) {
    return null;
  }

  const yearFirstMatch = YEAR_FIRST_DATE_PATTERN.exec(value);
  if (yearFirstMatch) {
    return buildIsoDate(Number(yearFirstMatch[1]), Number(yearFirstMatch[2]), Number(yearFirstMatch[3]));
  }

  const monthFirstMatch = MONTH_FIRST_DATE_PATTERN.exec(value);
  if (monthFirstMatch) {
    return buildIsoDate(Number(monthFirstMatch[3]), Number(monthFirstMatch[1]), Number(monthFirstMatch[2]));
  }

  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) {
    return buildIsoDate(parsed.getUTCFullYear(), parsed.getUTCMonth() + 1, parsed.getUTCDate());
  }

  return null;
}

export function compareIsoDates(a: string, b: string): number {
  return a.localeCompare(b);
}

export function getAggregateRecordDateRange(
  records: Pick<AggregateTimeSeriesRecord, "date">[]
): AggregateTimeSeriesDateRange | null {
  if (records.length === 0) {
    return null;
  }

  const sortedDates = records.map((record) => record.date).sort(compareIsoDates);
  return {
    startDate: sortedDates[0],
    endDate: sortedDates[sortedDates.length - 1]
  };
}

export function isDateInAggregateRange(date: string, range: AggregateTimeSeriesDateRangeSelection): boolean {
  if (range.startDate && compareIsoDates(date, range.startDate) < 0) {
    return false;
  }

  if (range.endDate && compareIsoDates(date, range.endDate) > 0) {
    return false;
  }

  return true;
}

export function filterAggregateRecordsByDateRange<T extends Pick<AggregateTimeSeriesRecord, "date">>(
  records: T[],
  range: AggregateTimeSeriesDateRangeSelection
): T[] {
  if (!range.startDate && !range.endDate) {
    return records;
  }

  return records.filter((record) => isDateInAggregateRange(record.date, range));
}

export function sortAggregateRecordsByDate<T extends Pick<AggregateTimeSeriesRecord, "date">>(records: T[]): T[] {
  return [...records].sort((a, b) => compareIsoDates(a.date, b.date));
}
