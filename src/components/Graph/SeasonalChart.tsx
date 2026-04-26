// Year-over-year / season-over-season chart mode.
//
// Same metric / filter inputs as the time-series chart, but the X axis
// becomes "position within period" (day-of-period 0 → ~365) and each
// completed period becomes its own line. Color encodes recency: the most
// recent period is fully saturated; older periods desaturate / fade.
//
// v1 scope (per FOLLOW_UPS #2):
//   - calendar-year, flu-season (north/south), calendar-month, fiscal-year
//     period kinds available.
//   - Reuses Metric + Filters from the parent SourceTimelineChart toolbar.
//   - Split-by is *not* applied here — combining N split-keys × M periods
//     would explode the line count. Filter pre-applies the split column
//     instead. Surfacing split-by in seasonal mode is a v2 follow-up.
//   - Partial / in-progress current period: no special "thru-W14"
//     annotation yet — line just stops where the data stops, which is
//     visually correct.

import { useMemo } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  dateToPeriod,
  formatPeriodTick,
  periodLengthDays,
  sortPeriodIdsNewestFirst,
  type PeriodKind
} from "../../data/periods";
import { aggregate, type AggregationMethod } from "../../data/aggregation";
import type { DatasetRow } from "../../data/hf/rows";

interface ActiveFilter {
  name: string;
  value: string;
}

const ALL = "__all__";

interface Props {
  rows: DatasetRow[];
  dateField: string | null;
  metric: string | null;
  aggMethod: AggregationMethod;
  periodKind: PeriodKind;
  activeFilters: ActiveFilter[];
}

/**
 * Pure bucketing logic, extracted for unit testing. Takes raw rows + a
 * period kind and returns the data shape Recharts wants (one row per
 * xIndex, one column per periodId) plus the ordered period list.
 */
export function buildSeasonalChartData(args: {
  rows: DatasetRow[];
  dateField: string;
  metric: string;
  aggMethod: AggregationMethod;
  periodKind: PeriodKind;
  activeFilters: ActiveFilter[];
}): { chartData: Record<string, number>[]; periodIds: string[] } {
  const { rows, dateField, metric, aggMethod, periodKind, activeFilters } = args;
  const buckets = new Map<number, Map<string, number[]>>();
  const seenPeriods = new Set<string>();

  for (const row of rows) {
    let skip = false;
    for (const f of activeFilters) {
      if (f.value === ALL) continue;
      if (String(row[f.name] ?? "") !== f.value) {
        skip = true;
        break;
      }
    }
    if (skip) continue;

    const dateRaw = row[dateField];
    if (typeof dateRaw !== "string" || !dateRaw) continue;
    const d = new Date(dateRaw);
    if (Number.isNaN(d.getTime())) continue;

    const valueRaw = row[metric];
    const value = typeof valueRaw === "number" ? valueRaw : Number(valueRaw);
    if (!Number.isFinite(value)) continue;

    const { periodId, xIndex } = dateToPeriod(d, periodKind);
    seenPeriods.add(periodId);
    let xMap = buckets.get(xIndex);
    if (!xMap) {
      xMap = new Map();
      buckets.set(xIndex, xMap);
    }
    let arr = xMap.get(periodId);
    if (!arr) {
      arr = [];
      xMap.set(periodId, arr);
    }
    arr.push(value);
  }

  const periodIds = sortPeriodIdsNewestFirst(Array.from(seenPeriods));
  const xs = Array.from(buckets.keys()).sort((a, b) => a - b);
  const chartData = xs.map((x) => {
    const xMap = buckets.get(x)!;
    const row: Record<string, number> = { x };
    for (const pid of periodIds) {
      const values = xMap.get(pid);
      if (values && values.length > 0) row[pid] = aggregate(values, aggMethod);
    }
    return row;
  });

  return { chartData, periodIds };
}

export function SeasonalChart({ rows, dateField, metric, aggMethod, periodKind, activeFilters }: Props) {
  const { chartData, periodIds } = useMemo(() => {
    if (!dateField || !metric) return { chartData: [], periodIds: [] as string[] };
    return buildSeasonalChartData({ rows, dateField, metric, aggMethod, periodKind, activeFilters });
  }, [rows, dateField, metric, aggMethod, periodKind, activeFilters]);

  if (!metric || !dateField) {
    return (
      <Empty body="Pick a metric to see the seasonal overlay." />
    );
  }
  if (chartData.length === 0 || periodIds.length === 0) {
    return (
      <Empty body="No periods detected — does the dataset cover at least one full period of the selected kind?" />
    );
  }

  const xMax = periodLengthDays(periodKind);
  // Color stops: most recent fully saturated, older fade through to faint.
  const colorByPeriodId = buildColorByRecency(periodIds);

  return (
    <div className="h-[400px] rounded-lg border border-white/10 bg-neutral-950 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <CartesianGrid stroke="rgba(255,255,255,0.06)" />
          <XAxis
            dataKey="x"
            type="number"
            domain={[0, xMax]}
            tick={{ fill: "#cbd5e1", fontSize: 11 }}
            tickFormatter={(x: number) => formatPeriodTick(x, periodKind)}
          />
          <YAxis
            tick={{ fill: "#cbd5e1", fontSize: 11 }}
            tickFormatter={(v: number) => v.toLocaleString()}
          />
          <Tooltip
            contentStyle={{ background: "rgba(15,23,42,0.95)", border: "1px solid rgba(255,255,255,0.1)" }}
            labelFormatter={(x: number) => formatPeriodTick(x, periodKind)}
            formatter={(v: number) => v.toLocaleString()}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: "#cbd5e1" }} />
          {periodIds.map((pid) => (
            <Line
              key={pid}
              type="monotone"
              dataKey={pid}
              stroke={colorByPeriodId.get(pid)}
              strokeWidth={pid === periodIds[0] ? 2 : 1}
              dot={false}
              // Seasonal data is intrinsically sparse along the shared X
              // axis — different years' weekly cadences land on different
              // days-of-year, so a chart row that has 2024's value will be
              // missing 2023's. With connectNulls=false + dot=false, every
              // defined point sits between two undefined neighbours and
              // Recharts draws no segment — the line vanishes. With
              // connectNulls=true each period's line threads through all
              // its own defined points, skipping rows that belong to other
              // periods. Real intra-period gaps (a missing week) get
              // bridged silently — acceptable for an overlay-comparison view.
              connectNulls={true}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Color stops for period-recency encoding. Most recent period gets the
 * dashboard's primary sky-500; older periods desaturate toward gray.
 *
 * Implementation note: we generate one HSL color per period, sliding L
 * up (lighter / more faded) and S down (less saturated) as we go older.
 */
function buildColorByRecency(periodIdsNewestFirst: string[]): Map<string, string> {
  const map = new Map<string, string>();
  const n = periodIdsNewestFirst.length;
  if (n === 0) return map;

  // Anchors: newest = sky-500-ish (200° hue, full saturation), oldest = gray.
  const HUE = 200;
  for (let i = 0; i < n; i++) {
    const t = n === 1 ? 0 : i / (n - 1); // 0 = newest, 1 = oldest
    // Saturation: 80% → 15%
    const s = Math.round(80 - 65 * t);
    // Lightness: 55% → 70% (lighter / less prominent for old)
    const l = Math.round(55 + 15 * t);
    map.set(periodIdsNewestFirst[i], `hsl(${HUE}, ${s}%, ${l}%)`);
  }
  return map;
}

function Empty({ body }: { body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-white/15 bg-white/[0.02] p-6 text-center text-sm text-neutral-400">
      {body}
    </div>
  );
}
