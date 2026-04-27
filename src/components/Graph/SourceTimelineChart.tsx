import { useEffect, useMemo, useRef, useState } from "react";
import { ListFilter, Plus, X } from "lucide-react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipProps
} from "recharts";
import { detectCategoricalFields, detectDateField, detectNumericFields, type DatasetRow } from "../../data/hf/rows";
import { aggregate, aggregationLabel, pickAggregation, type AggregationMethod } from "../../data/aggregation";
import { BUILTIN_PERIOD_KINDS, periodKindLabel, type PeriodKind } from "../../data/periods";
import type { SourceMetadata, ValueColumn } from "../../types/source";
import { SeasonalChart } from "./SeasonalChart";
import type { ParsedPredictions } from "../../data/predictions/companion";

const PREDICTION_SERIES_PREFIX = "pred:";
const PREDICTION_BAND_PREFIX = "band80:";

// Distinct from the truth/split-by palette so a prediction line never
// collides with a truth series at a glance. Warm-leaning colors paired
// with a dashed stroke read clearly as "forecast" against the cool truth
// series the chart already uses.
const PREDICTION_COLORS = [
  "#fbbf24", // amber-400
  "#f472b6", // pink-400
  "#a78bfa", // violet-400
  "#fb923c", // orange-400
  "#34d399"  // emerald-400 (lighter)
];

export function predictionColorFor(submitters: string[]): Record<string, string> {
  const out: Record<string, string> = {};
  const sorted = [...submitters].sort();
  for (let i = 0; i < sorted.length; i++) {
    out[sorted[i]] = PREDICTION_COLORS[i % PREDICTION_COLORS.length];
  }
  return out;
}

export interface PredictionsOverlay {
  parsed: ParsedPredictions;
  selectedSubmitters: Set<string>;
  colorBySubmitter: Record<string, string>;
}

interface Props {
  source: SourceMetadata;
  rows: DatasetRow[];
  predictions?: PredictionsOverlay;
  /**
   * Currently selected metric (Y-axis column). Controlled — parent owns
   * the state. Pass `null` to defer until the chart proposes a default
   * via `onMetricChange`.
   */
  metric: string | null;
  onMetricChange: (metric: string | null) => void;
  /** Active categorical filters. Controlled. */
  activeFilters: ActiveFilter[];
  onActiveFiltersChange: (filters: ActiveFilter[]) => void;
}

export const ALL_FILTER = "__all__";
const ALL = ALL_FILTER;
const NO_GROUP = "__none__";
const ROW_LEVEL_NON_FILTERS = ["location_id_native", "location_name", "as_of"];
const TOP_N_DEFAULT = 8;

export interface ActiveFilter {
  name: string;
  value: string;
}

// Distinct enough at small sizes; cycles for >8 groups.
const SERIES_COLORS = [
  "#0ea5e9", // red
  "#3b82f6", // blue
  "#10b981", // emerald
  "#f59e0b", // amber
  "#a855f7", // violet
  "#ec4899", // pink
  "#14b8a6", // teal
  "#f97316"  // orange
];

const SINGLE_SERIES_KEY = "All";

export function SourceTimelineChart({
  source,
  rows,
  predictions,
  metric,
  onMetricChange,
  activeFilters,
  onActiveFiltersChange
}: Props) {
  const dateField = useMemo(() => detectDateField(rows), [rows]);

  const declaredNumeric = source.value_columns
    .filter((c) => c.dtype === "int" || c.dtype === "float")
    .map((c) => c.name);
  const detectedNumeric = useMemo(
    () => detectNumericFields(rows, [dateField ?? "", ...ROW_LEVEL_NON_FILTERS]),
    [rows, dateField]
  );
  const numericFields = declaredNumeric.length > 0 ? declaredNumeric : detectedNumeric;

  // Categorical columns — used for both filters and group-by candidates.
  const categoricalFields = useMemo(
    () =>
      detectCategoricalFields(rows, [
        dateField ?? "",
        ...numericFields,
        ...ROW_LEVEL_NON_FILTERS
      ]),
    [rows, dateField, numericFields]
  );

  // Default-metric proposal: when parent passes `metric=null`, propose the
  // first numeric field. We don't repair "metric set to a column not in
  // numericFields" — parent may be pinning to a known column we haven't
  // detected yet (e.g. the predictions overlay's target_column).
  useEffect(() => {
    if (metric === null && numericFields.length > 0) onMetricChange(numericFields[0]);
  }, [metric, numericFields, onMetricChange]);

  const [groupBy, setGroupBy] = useState<string>(NO_GROUP);
  // Drop group-by if its column disappears.
  useEffect(() => {
    if (groupBy !== NO_GROUP && !categoricalFields.some((f) => f.name === groupBy)) {
      setGroupBy(NO_GROUP);
    }
  }, [categoricalFields, groupBy]);

  // Chart mode: time series (default) or seasonal (year-over-year overlay).
  // Persisted only in component state for v1; promoting to pane state lives
  // in FOLLOW_UPS #2's "what can be deferred" list.
  const [chartMode, setChartMode] = useState<"time-series" | "seasonal">("time-series");
  const [periodKindIdx, setPeriodKindIdx] = useState<number>(0); // index into BUILTIN_PERIOD_KINDS
  const periodKind = BUILTIN_PERIOD_KINDS[periodKindIdx];

  // First-time filter seed: when categoricalFields first arrive and parent
  // hasn't supplied any filters, default to a `location_id = ALL` filter
  // if that column exists. Mirrors the previous internal behavior.
  const initFilterRef = useRef(false);
  useEffect(() => {
    if (initFilterRef.current) return;
    if (categoricalFields.length === 0) return;
    if (activeFilters.length > 0) {
      initFilterRef.current = true;
      return;
    }
    initFilterRef.current = true;
    if (categoricalFields.some((f) => f.name === "location_id")) {
      onActiveFiltersChange([{ name: "location_id", value: ALL }]);
    }
  }, [categoricalFields, activeFilters, onActiveFiltersChange]);

  // Repair filters when the categorical schema changes (drop missing
  // columns, coerce stale values to ALL).
  useEffect(() => {
    const next = activeFilters
      .filter((f) => categoricalFields.some((ff) => ff.name === f.name))
      .map((f) => {
        const field = categoricalFields.find((ff) => ff.name === f.name)!;
        if (f.value === ALL || field.values.includes(f.value)) return f;
        return { ...f, value: ALL };
      });
    const changed =
      next.length !== activeFilters.length ||
      next.some((f, i) => f.value !== activeFilters[i].value);
    if (changed) onActiveFiltersChange(next);
  }, [categoricalFields, activeFilters, onActiveFiltersChange]);

  const availableForAdd = useMemo(
    () => categoricalFields.filter((f) => !activeFilters.some((af) => af.name === f.name)),
    [categoricalFields, activeFilters]
  );

  const addFilter = (name: string) => {
    if (!categoricalFields.some((f) => f.name === name)) return;
    if (activeFilters.some((f) => f.name === name)) return;
    onActiveFiltersChange([...activeFilters, { name, value: ALL }]);
  };
  const removeFilter = (name: string) =>
    onActiveFiltersChange(activeFilters.filter((f) => f.name !== name));
  const setFilterValue = (name: string, value: string) =>
    onActiveFiltersChange(activeFilters.map((f) => (f.name === name ? { ...f, value } : f)));

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!menuOpen) return;
    const onMouseDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const valueColumnMeta = source.value_columns.find((c) => c.name === metric);
  const aggMethod = pickAggregation(valueColumnMeta);

  // Aggregate matching rows by (groupKey, date) using the column's declared
  // aggregation — single line by default, multiple lines when groupBy is set.
  // When `predictions` is supplied, also folds per-submitter point estimates
  // into the same chartData under `pred:<submitter>` keys.
  const { chartData, groupKeys, colorByGroup, groupTotals, renderedPredictionSubmitters } = useMemo(() => {
    if (!dateField || !metric)
      return {
        chartData: [],
        groupKeys: [] as string[],
        colorByGroup: {} as Record<string, string>,
        groupTotals: new Map<string, number>(),
        renderedPredictionSubmitters: [] as string[]
      };

    const buckets = new Map<string, Map<string, number[]>>(); // groupKey → date → values
    const allDates = new Set<string>();
    for (const row of rows) {
      let passes = true;
      for (const f of activeFilters) {
        if (f.value === ALL) continue;
        if (String(row[f.name] ?? "") !== f.value) {
          passes = false;
          break;
        }
      }
      if (!passes) continue;

      const dateRaw = row[dateField];
      const date = typeof dateRaw === "string" ? dateRaw.slice(0, 10) : String(dateRaw ?? "");
      if (!date) continue;
      const valueRaw = row[metric];
      const value = typeof valueRaw === "number" ? valueRaw : Number(valueRaw);
      if (!Number.isFinite(value)) continue;

      const groupKey = groupBy === NO_GROUP ? SINGLE_SERIES_KEY : String(row[groupBy] ?? "(unknown)");

      let g = buckets.get(groupKey);
      if (!g) {
        g = new Map();
        buckets.set(groupKey, g);
      }
      let arr = g.get(date);
      if (!arr) {
        arr = [];
        g.set(date, arr);
      }
      arr.push(value);
      allDates.add(date);
    }

    // Predictions overlay: gather point estimates and 80% interval bounds
    // (quantile 0.1 / 0.9) per (submitter, date) for selected submitters.
    // Loose dim filter — a prediction passes if every active truth filter
    // value appears somewhere in the row's dim columns. Slice C will
    // replace this with explicit dim mapping at the pane level.
    const predPointBuckets = new Map<string, Map<string, number[]>>();
    const predLowerBuckets = new Map<string, Map<string, number[]>>();
    const predUpperBuckets = new Map<string, Map<string, number[]>>();
    if (predictions && predictions.selectedSubmitters.size > 0) {
      const explicitFilterValues = activeFilters
        .filter((f) => f.value !== ALL)
        .map((f) => f.value);
      const pushBucket = (
        bucket: Map<string, Map<string, number[]>>,
        submitter: string,
        date: string,
        v: number
      ) => {
        let bySubmitter = bucket.get(submitter);
        if (!bySubmitter) {
          bySubmitter = new Map();
          bucket.set(submitter, bySubmitter);
        }
        let arr = bySubmitter.get(date);
        if (!arr) {
          arr = [];
          bySubmitter.set(date, arr);
        }
        arr.push(v);
      };
      for (const pr of predictions.parsed.rows) {
        if (!predictions.selectedSubmitters.has(pr.submitter)) continue;
        if (explicitFilterValues.length > 0) {
          const dimValues = Object.values(pr.dims);
          const matches = explicitFilterValues.every((v) => dimValues.includes(v));
          if (!matches) continue;
        }
        if (pr.quantile === null) {
          pushBucket(predPointBuckets, pr.submitter, pr.date, pr.value);
        } else if (Math.abs(pr.quantile - 0.1) < 1e-3) {
          pushBucket(predLowerBuckets, pr.submitter, pr.date, pr.value);
        } else if (Math.abs(pr.quantile - 0.9) < 1e-3) {
          pushBucket(predUpperBuckets, pr.submitter, pr.date, pr.value);
        }
        allDates.add(pr.date);
      }
    }

    const groupKeys = Array.from(buckets.keys()).sort();
    const renderedPredictionSubmitters = Array.from(predPointBuckets.keys()).sort();
    const sortedDates = Array.from(allDates).sort();
    const mean = (arr: number[]): number => arr.reduce((a, b) => a + b, 0) / arr.length;

    // Aggregate per (group, date) and accumulate per-group totals for ranking.
    const groupTotals = new Map<string, number>();
    const chartData = sortedDates.map((date) => {
      const out: Record<string, string | number | [number, number] | null> = { date };
      for (const groupKey of groupKeys) {
        const values = buckets.get(groupKey)?.get(date);
        if (values && values.length > 0) {
          const v = aggregate(values, aggMethod);
          out[groupKey] = v;
          if (Number.isFinite(v)) groupTotals.set(groupKey, (groupTotals.get(groupKey) ?? 0) + (v as number));
        } else {
          out[groupKey] = null;
        }
      }
      // Predictions: mean across multiple model runs for the same submitter
      // on the same date (most submitters will have exactly one).
      for (const submitter of renderedPredictionSubmitters) {
        const points = predPointBuckets.get(submitter)?.get(date);
        const lowers = predLowerBuckets.get(submitter)?.get(date);
        const uppers = predUpperBuckets.get(submitter)?.get(date);
        out[`${PREDICTION_SERIES_PREFIX}${submitter}`] =
          points && points.length > 0 ? mean(points) : null;
        // 80% interval as a [lower, upper] tuple — recharts Area renders
        // this natively when the dataKey returns a 2-element array.
        const band: [number, number] | null =
          lowers && lowers.length > 0 && uppers && uppers.length > 0
            ? [mean(lowers), mean(uppers)]
            : null;
        out[`${PREDICTION_BAND_PREFIX}${submitter}`] = band;
      }
      return out;
    });

    // Colors keyed by name so a series stays the same color regardless of
    // which siblings are currently visible.
    const colorByGroup: Record<string, string> = {};
    if (groupKeys.length === 1 && groupKeys[0] === SINGLE_SERIES_KEY) {
      colorByGroup[SINGLE_SERIES_KEY] = SERIES_COLORS[0];
    } else {
      for (let i = 0; i < groupKeys.length; i++) {
        colorByGroup[groupKeys[i]] = SERIES_COLORS[i % SERIES_COLORS.length];
      }
    }
    return { chartData, groupKeys, colorByGroup, groupTotals, renderedPredictionSubmitters };
  }, [rows, dateField, metric, activeFilters, groupBy, aggMethod, predictions]);

  // Visible-series state. When the group-by axis changes, default to the top
  // TOP_N_DEFAULT groups by total value so we don't drown the chart in lines.
  // null = "show all" (used when groupKeys.length <= TOP_N_DEFAULT).
  const [visibleGroupKeys, setVisibleGroupKeys] = useState<Set<string> | null>(null);
  const groupKeysSig = groupKeys.join("|");
  useEffect(() => {
    if (groupKeys.length === 0) {
      setVisibleGroupKeys(null);
      return;
    }
    if (groupKeys.length <= TOP_N_DEFAULT) {
      setVisibleGroupKeys(null);
      return;
    }
    const ranked = [...groupKeys].sort((a, b) => (groupTotals.get(b) ?? 0) - (groupTotals.get(a) ?? 0));
    setVisibleGroupKeys(new Set(ranked.slice(0, TOP_N_DEFAULT)));
    // Reset only when the set of group keys actually changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [groupKeysSig]);

  const renderedGroupKeys = useMemo(() => {
    if (!visibleGroupKeys) return groupKeys;
    return groupKeys.filter((k) => visibleGroupKeys.has(k));
  }, [groupKeys, visibleGroupKeys]);

  const toggleGroupVisible = (key: string) => {
    setVisibleGroupKeys((curr) => {
      const base = curr ?? new Set(groupKeys);
      const next = new Set(base);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const resetToTopN = () => {
    const ranked = [...groupKeys].sort((a, b) => (groupTotals.get(b) ?? 0) - (groupTotals.get(a) ?? 0));
    setVisibleGroupKeys(new Set(ranked.slice(0, TOP_N_DEFAULT)));
  };

  // Series picker popover.
  const [seriesMenuOpen, setSeriesMenuOpen] = useState(false);
  const seriesMenuRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!seriesMenuOpen) return;
    const onMouseDown = (e: MouseEvent) => {
      if (seriesMenuRef.current && !seriesMenuRef.current.contains(e.target as Node)) setSeriesMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSeriesMenuOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [seriesMenuOpen]);

  if (!dateField) return <Empty body="No date column detected on this dataset." />;
  if (numericFields.length === 0) return <Empty body="No numeric metrics declared or detected." />;

  const showLegend =
    (groupBy !== NO_GROUP && renderedGroupKeys.length > 1) ||
    renderedPredictionSubmitters.length > 0;
  const aggLabel = aggregationLabel(aggMethod, valueColumnMeta?.aggregation);
  const seriesPickerActive = groupBy !== NO_GROUP && groupKeys.length > TOP_N_DEFAULT;

  return (
    <div className="space-y-3">
      {/* Chart-mode toggle: time-series vs seasonal overlay. Sits above the
          Metric/Split-by/Filters row so the user can flip without losing
          their column / filter selections. */}
      <div className="flex items-center gap-2 text-xs">
        <div className="inline-flex rounded-md border border-white/10 bg-white/[0.03] p-0.5">
          <button
            type="button"
            onClick={() => setChartMode("time-series")}
            aria-pressed={chartMode === "time-series"}
            className={`rounded px-2 py-1 transition ${
              chartMode === "time-series"
                ? "bg-sky-700/40 text-sky-100"
                : "text-neutral-300 hover:text-white"
            }`}
          >
            Time series
          </button>
          <button
            type="button"
            onClick={() => setChartMode("seasonal")}
            aria-pressed={chartMode === "seasonal"}
            className={`rounded px-2 py-1 transition ${
              chartMode === "seasonal"
                ? "bg-sky-700/40 text-sky-100"
                : "text-neutral-300 hover:text-white"
            }`}
          >
            Seasonal
          </button>
        </div>
        {chartMode === "seasonal" && (
          <label className="flex items-center gap-1 text-[10px] uppercase text-neutral-400">
            Period
            <select
              value={periodKindIdx}
              onChange={(e) => setPeriodKindIdx(Number(e.target.value))}
              className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-xs normal-case text-white"
            >
              {BUILTIN_PERIOD_KINDS.map((k, i) => (
                <option key={i} value={i}>
                  {periodKindLabel(k)}
                </option>
              ))}
            </select>
          </label>
        )}
        {chartMode === "seasonal" && groupBy !== NO_GROUP && (
          <span className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-200">
            Split-by ignored in seasonal mode (v1)
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-start gap-3 text-xs">
        {/* Metric */}
        <div className="flex min-h-[92px] min-w-[160px] flex-col gap-1 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
          <span className="text-[10px] font-semibold uppercase text-neutral-400">Metric (Y axis)</span>
          <select
            value={metric ?? ""}
            onChange={(e) => onMetricChange(e.target.value)}
            disabled={Boolean(predictions)}
            title={
              predictions
                ? "Pinned to the predictions' target column while the overlay is on"
                : undefined
            }
            className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-white disabled:cursor-not-allowed disabled:opacity-70"
          >
            {numericFields.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
            {/* If the parent pinned to a column outside numericFields
                (e.g. predictions targeting an undeclared column), include
                it in the option list so the select displays it. */}
            {metric && !numericFields.includes(metric) && (
              <option value={metric}>{metric}</option>
            )}
          </select>
          <div className="mt-auto flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-neutral-400">
            {valueColumnMeta?.unit && (
              <span>
                unit: <span className="text-neutral-200">{valueColumnMeta.unit}</span>
              </span>
            )}
            {valueColumnMeta?.value_type && (
              <span>
                type: <span className="text-neutral-200">{valueColumnMeta.value_type}</span>
              </span>
            )}
            <span>
              agg: <span className="text-neutral-200">{aggLabel}</span>
            </span>
          </div>
        </div>

        {/* Split by (formerly "Group by") */}
        {categoricalFields.length > 0 && (
          <div className="flex min-h-[92px] min-w-[160px] flex-col gap-1 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
            <span className="text-[10px] font-semibold uppercase text-neutral-400">Split by</span>
            <select
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value)}
              className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-white"
            >
              <option value={NO_GROUP}>None</option>
              {categoricalFields.map((f) => (
                <option key={f.name} value={f.name}>
                  {f.name}
                </option>
              ))}
            </select>
            <div className="mt-auto flex items-center justify-between gap-2 text-[10px] text-neutral-400">
              {groupBy !== NO_GROUP ? (
                <>
                  <span>
                    {seriesPickerActive
                      ? `${renderedGroupKeys.length} of ${groupKeys.length} series`
                      : `${groupKeys.length} ${groupKeys.length === 1 ? "series" : "series"}`}
                  </span>
                  {seriesPickerActive && (
                  <div className="relative" ref={seriesMenuRef}>
                    <button
                      type="button"
                      onClick={() => setSeriesMenuOpen((o) => !o)}
                      title="Pick which series to show"
                      aria-label="Pick series"
                      aria-haspopup="menu"
                      aria-expanded={seriesMenuOpen}
                      className="flex items-center gap-1 rounded border border-white/10 px-1.5 py-0.5 text-neutral-200 hover:border-sky-500 hover:text-sky-200"
                    >
                      <ListFilter className="h-3 w-3" />
                      Pick
                    </button>
                    {seriesMenuOpen && (
                      <SeriesPicker
                        groupKeys={groupKeys}
                        groupTotals={groupTotals}
                        visibleSet={visibleGroupKeys ?? new Set(groupKeys)}
                        colorByGroup={colorByGroup}
                        onToggle={toggleGroupVisible}
                        onResetTopN={resetToTopN}
                      />
                    )}
                  </div>
                )}
                </>
              ) : (
                // Empty bottom slot keeps the box height consistent with
                // the Metric panel and aligns the select control across boxes.
                <span aria-hidden="true">&nbsp;</span>
              )}
            </div>
          </div>
        )}

        {/* Filters: each chip is a self-contained label+select mini-panel,
            visually parallel to Metric / Split by. The `+` button sits in
            the same shape (label above, control below) so its position
            matches the selects in the other boxes. */}
        {(categoricalFields.length > 0 || activeFilters.length > 0) && (
          <div className="flex min-h-[92px] flex-wrap items-start gap-2 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold uppercase text-neutral-400">Filter</span>
              <div className="relative" ref={menuRef}>
                <button
                  type="button"
                  onClick={() => setMenuOpen((o) => !o)}
                  disabled={availableForAdd.length === 0}
                  title={availableForAdd.length === 0 ? "All filterable columns are active" : "Add filter"}
                  aria-label="Add filter"
                  aria-haspopup="menu"
                  aria-expanded={menuOpen}
                  className="flex h-[28px] w-[28px] items-center justify-center rounded-md border border-white/15 bg-white/[0.04] text-neutral-300 transition hover:border-sky-500 hover:text-sky-200 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-white/15 disabled:hover:text-neutral-300"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
                {menuOpen && availableForAdd.length > 0 && (
                  <div
                    role="menu"
                    className="absolute left-0 top-full z-20 mt-1 max-h-64 min-w-[180px] overflow-y-auto rounded-md border border-white/10 bg-black/95 p-1 shadow-lg backdrop-blur"
                  >
                    <p className="px-2 py-1 text-[10px] font-semibold uppercase text-neutral-500">Add filter</p>
                    {availableForAdd.map((col) => (
                      <button
                        key={col.name}
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          addFilter(col.name);
                          setMenuOpen(false);
                        }}
                        className="flex w-full items-center justify-between gap-2 rounded px-2 py-1 text-left text-xs text-neutral-200 hover:bg-white/10 hover:text-white"
                      >
                        <span className="truncate">{col.name}</span>
                        <span className="shrink-0 text-[10px] text-neutral-500">{col.values.length}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {activeFilters.map((filter) => {
              const field = categoricalFields.find((f) => f.name === filter.name);
              if (!field) return null;
              return (
                <div key={filter.name} className="flex min-w-[120px] flex-col gap-1">
                  <div className="flex items-center justify-between gap-1">
                    <span
                      className="truncate text-[10px] font-semibold uppercase text-neutral-400"
                      title={filter.name}
                    >
                      {filter.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeFilter(filter.name)}
                      className="rounded p-0.5 text-neutral-500 hover:bg-white/10 hover:text-white"
                      aria-label={`Remove ${filter.name} filter`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                  <select
                    value={filter.value}
                    onChange={(e) => setFilterValue(filter.name, e.target.value)}
                    className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-white"
                  >
                    <option value={ALL}>All ({field.values.length})</option>
                    {field.values.map((v) => (
                      <option key={v} value={v}>
                        {v}
                      </option>
                    ))}
                  </select>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {chartMode === "seasonal" ? (
        <SeasonalChart
          rows={rows}
          dateField={dateField}
          metric={metric}
          aggMethod={aggMethod}
          periodKind={periodKind}
          activeFilters={activeFilters}
        />
      ) : chartData.length === 0 || renderedGroupKeys.length === 0 ? (
        <Empty
          body={
            chartData.length === 0
              ? "No rows match the current filters."
              : "No series visible — pick at least one in the Split by panel."
          }
        />
      ) : (
        <div className="h-[400px] rounded-lg border border-white/10 bg-neutral-950 p-3">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#262626" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#a3a3a3", fontSize: 12 }} minTickGap={28} stroke="#404040" />
              <YAxis tick={{ fill: "#a3a3a3", fontSize: 12 }} stroke="#404040" />
              <Tooltip
                content={
                  <HoverCard
                    groupKeys={renderedGroupKeys}
                    colorByGroup={colorByGroup}
                    predictionColors={predictions?.colorBySubmitter ?? {}}
                  />
                }
                cursor={{ stroke: "#525252", strokeWidth: 1 }}
              />
              {showLegend && (
                <Legend
                  wrapperStyle={{ fontSize: 11, color: "#d4d4d8", paddingTop: 6 }}
                  iconType="plainline"
                />
              )}
              {renderedGroupKeys.map((g) => (
                <Line
                  key={g}
                  type="monotone"
                  dataKey={g}
                  stroke={colorByGroup[g]}
                  strokeWidth={2.2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))}
              {renderedPredictionSubmitters.map((submitter) => (
                <Area
                  key={`${PREDICTION_BAND_PREFIX}${submitter}`}
                  dataKey={`${PREDICTION_BAND_PREFIX}${submitter}`}
                  name={`${submitter} 80%`}
                  legendType="none"
                  stroke="none"
                  fill={predictions?.colorBySubmitter[submitter] ?? "#fbbf24"}
                  fillOpacity={0.18}
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
              {renderedPredictionSubmitters.map((submitter) => (
                <Line
                  key={`${PREDICTION_SERIES_PREFIX}${submitter}`}
                  type="monotone"
                  dataKey={`${PREDICTION_SERIES_PREFIX}${submitter}`}
                  name={`${submitter} (forecast)`}
                  stroke={predictions?.colorBySubmitter[submitter] ?? "#fbbf24"}
                  strokeWidth={1.8}
                  strokeDasharray="6 3"
                  dot={false}
                  activeDot={{ r: 3 }}
                  connectNulls
                  isAnimationActive={false}
                />
              ))}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

interface SeriesPickerProps {
  groupKeys: string[];
  groupTotals: Map<string, number>;
  visibleSet: Set<string>;
  colorByGroup: Record<string, string>;
  onToggle: (key: string) => void;
  onResetTopN: () => void;
}

function SeriesPicker({ groupKeys, groupTotals, visibleSet, colorByGroup, onToggle, onResetTopN }: SeriesPickerProps) {
  const ranked = [...groupKeys].sort((a, b) => (groupTotals.get(b) ?? 0) - (groupTotals.get(a) ?? 0));
  const [query, setQuery] = useState("");
  const filtered = query
    ? ranked.filter((k) => k.toLowerCase().includes(query.toLowerCase()))
    : ranked;

  return (
    <div
      role="menu"
      className="absolute right-0 top-full z-30 mt-1 w-[260px] rounded-md border border-white/10 bg-black/95 p-2 shadow-lg backdrop-blur"
    >
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase text-neutral-400">Pick series</p>
        <button
          type="button"
          onClick={onResetTopN}
          className="text-[10px] text-neutral-400 hover:text-sky-200"
        >
          Reset to top {TOP_N_DEFAULT}
        </button>
      </div>
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search…"
        className="mt-2 w-full rounded border border-white/10 bg-black/60 px-2 py-1 text-xs text-white placeholder:text-neutral-500 focus:border-sky-500 focus:outline-none"
      />
      <ul className="mt-2 max-h-[260px] space-y-0.5 overflow-y-auto pr-1">
        {filtered.map((g) => {
          const total = groupTotals.get(g) ?? 0;
          const checked = visibleSet.has(g);
          return (
            <li key={g}>
              <label
                className={`flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs transition ${
                  checked ? "text-white" : "text-neutral-300 hover:bg-white/5"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onToggle(g)}
                  className="accent-sky-500"
                />
                <span
                  aria-hidden="true"
                  className="inline-block h-2 w-2 shrink-0 rounded-sm"
                  style={{ background: colorByGroup[g] ?? "#0ea5e9", opacity: checked ? 1 : 0.4 }}
                />
                <span className="flex-1 truncate" title={g}>
                  {g}
                </span>
                <span className="ml-auto shrink-0 font-mono text-[10px] text-neutral-500">
                  {Number.isFinite(total) ? total.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}
                </span>
              </label>
            </li>
          );
        })}
        {filtered.length === 0 && (
          <li className="px-2 py-1 text-xs text-neutral-500">No matches.</li>
        )}
      </ul>
    </div>
  );
}

function HoverCard({
  groupKeys,
  colorByGroup,
  predictionColors,
  active,
  payload,
  label
}: TooltipProps<number, string> & {
  groupKeys: string[];
  colorByGroup: Record<string, string>;
  predictionColors: Record<string, string>;
}) {
  if (!active || !payload?.length) return null;
  // Filter to entries we want to display: skip band tuples (formatted as
  // a "(80% interval)" suffix on the corresponding point line instead of
  // their own tooltip row).
  const displayable = payload.filter((p) => !String(p.dataKey).startsWith(PREDICTION_BAND_PREFIX));
  const sorted = [...displayable].sort((a, b) => Number(b.value ?? 0) - Number(a.value ?? 0));
  const showSeriesName = groupKeys.length > 1 || (groupKeys[0] && groupKeys[0] !== "All");
  // Lookup band tuple for each prediction submitter for inline display.
  const bandsBySubmitter = new Map<string, [number, number]>();
  for (const p of payload) {
    const key = String(p.dataKey);
    if (!key.startsWith(PREDICTION_BAND_PREFIX)) continue;
    const v = p.value as unknown;
    if (Array.isArray(v) && v.length === 2 && typeof v[0] === "number" && typeof v[1] === "number") {
      bandsBySubmitter.set(key.slice(PREDICTION_BAND_PREFIX.length), [v[0], v[1]]);
    }
  }
  return (
    <div className="rounded-md border border-white/10 bg-black/95 p-3 text-xs text-neutral-100 shadow-lg backdrop-blur">
      <p className="font-mono text-[10px] text-neutral-400">{String(label ?? "")}</p>
      <ul className="mt-1 space-y-0.5">
        {sorted.map((p) => {
          const key = String(p.dataKey);
          const value = p.value;
          if (value === null || value === undefined) return null;
          const isPrediction = key.startsWith(PREDICTION_SERIES_PREFIX);
          const submitter = isPrediction ? key.slice(PREDICTION_SERIES_PREFIX.length) : key;
          const color = isPrediction
            ? predictionColors[submitter] ?? "#fbbf24"
            : colorByGroup[key] ?? "#0ea5e9";
          const band = isPrediction ? bandsBySubmitter.get(submitter) : undefined;
          return (
            <li key={key} className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 rounded-sm"
                style={{ background: color }}
              />
              {(showSeriesName || isPrediction) && (
                <span className="text-neutral-200">
                  {isPrediction ? `${submitter} (forecast)` : key}:
                </span>
              )}
              <span className="font-mono text-neutral-100">
                {typeof value === "number" ? value.toLocaleString() : String(value)}
              </span>
              {band && (
                <span className="font-mono text-[10px] text-neutral-400">
                  [{band[0].toLocaleString(undefined, { maximumFractionDigits: 0 })} –{" "}
                  {band[1].toLocaleString(undefined, { maximumFractionDigits: 0 })}]
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Empty({ body }: { body: string }) {
  return <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">{body}</div>;
}
