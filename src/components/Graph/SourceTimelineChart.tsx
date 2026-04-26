import { useEffect, useMemo, useRef, useState } from "react";
import { ListFilter, Plus, X } from "lucide-react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import { detectCategoricalFields, detectDateField, detectNumericFields, type DatasetRow } from "../../data/hf/rows";
import { aggregate, aggregationLabel, pickAggregation, type AggregationMethod } from "../../data/aggregation";
import { BUILTIN_PERIOD_KINDS, periodKindLabel, type PeriodKind } from "../../data/periods";
import type { SourceMetadata, ValueColumn } from "../../types/source";
import { SeasonalChart } from "./SeasonalChart";

interface Props {
  source: SourceMetadata;
  rows: DatasetRow[];
}

const ALL = "__all__";
const NO_GROUP = "__none__";
const ROW_LEVEL_NON_FILTERS = ["location_id_native", "location_name", "as_of"];
const TOP_N_DEFAULT = 8;

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

interface ActiveFilter {
  name: string;
  value: string;
}

export function SourceTimelineChart({ source, rows }: Props) {
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

  const [metric, setMetric] = useState<string | null>(null);
  useEffect(() => {
    if (metric === null && numericFields.length > 0) setMetric(numericFields[0]);
    else if (metric !== null && !numericFields.includes(metric)) setMetric(numericFields[0] ?? null);
  }, [metric, numericFields]);

  const [groupBy, setGroupBy] = useState<string>(NO_GROUP);
  // Drop group-by if its column disappears.
  useEffect(() => {
    if (groupBy !== NO_GROUP && !categoricalFields.some((f) => f.name === groupBy)) {
      setGroupBy(NO_GROUP);
    }
  }, [categoricalFields, groupBy]);

  const [activeFilters, setActiveFilters] = useState<ActiveFilter[]>([]);

  // Chart mode: time series (default) or seasonal (year-over-year overlay).
  // Persisted only in component state for v1; promoting to pane state lives
  // in FOLLOW_UPS #2's "what can be deferred" list.
  const [chartMode, setChartMode] = useState<"time-series" | "seasonal">("time-series");
  const [periodKindIdx, setPeriodKindIdx] = useState<number>(0); // index into BUILTIN_PERIOD_KINDS
  const periodKind = BUILTIN_PERIOD_KINDS[periodKindIdx];

  const initRef = useRef(false);
  useEffect(() => {
    if (initRef.current || categoricalFields.length === 0) return;
    initRef.current = true;
    if (categoricalFields.some((f) => f.name === "location_id")) {
      setActiveFilters([{ name: "location_id", value: ALL }]);
    }
  }, [categoricalFields]);

  useEffect(() => {
    setActiveFilters((curr) => {
      const next = curr
        .filter((f) => categoricalFields.some((ff) => ff.name === f.name))
        .map((f) => {
          const field = categoricalFields.find((ff) => ff.name === f.name)!;
          if (f.value === ALL || field.values.includes(f.value)) return f;
          return { ...f, value: ALL };
        });
      return next.length === curr.length && next.every((f, i) => f.value === curr[i].value) ? curr : next;
    });
  }, [categoricalFields]);

  const availableForAdd = useMemo(
    () => categoricalFields.filter((f) => !activeFilters.some((af) => af.name === f.name)),
    [categoricalFields, activeFilters]
  );

  const addFilter = (name: string) => {
    if (!categoricalFields.some((f) => f.name === name)) return;
    setActiveFilters((curr) => (curr.some((f) => f.name === name) ? curr : [...curr, { name, value: ALL }]));
  };
  const removeFilter = (name: string) =>
    setActiveFilters((curr) => curr.filter((f) => f.name !== name));
  const setFilterValue = (name: string, value: string) =>
    setActiveFilters((curr) => curr.map((f) => (f.name === name ? { ...f, value } : f)));

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
  const { chartData, groupKeys, colorByGroup, groupTotals } = useMemo(() => {
    if (!dateField || !metric)
      return {
        chartData: [],
        groupKeys: [] as string[],
        colorByGroup: {} as Record<string, string>,
        groupTotals: new Map<string, number>()
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

    const groupKeys = Array.from(buckets.keys()).sort();
    const sortedDates = Array.from(allDates).sort();

    // Aggregate per (group, date) and accumulate per-group totals for ranking.
    const groupTotals = new Map<string, number>();
    const chartData = sortedDates.map((date) => {
      const out: Record<string, string | number | null> = { date };
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
    return { chartData, groupKeys, colorByGroup, groupTotals };
  }, [rows, dateField, metric, activeFilters, groupBy, aggMethod]);

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

  const showLegend = groupBy !== NO_GROUP && renderedGroupKeys.length > 1;
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
            onChange={(e) => setMetric(e.target.value)}
            className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-white"
          >
            {numericFields.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
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
            <LineChart data={chartData} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#262626" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#a3a3a3", fontSize: 12 }} minTickGap={28} stroke="#404040" />
              <YAxis tick={{ fill: "#a3a3a3", fontSize: 12 }} stroke="#404040" />
              <Tooltip
                content={<HoverCard groupKeys={renderedGroupKeys} colorByGroup={colorByGroup} />}
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
            </LineChart>
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
  active,
  payload,
  label
}: TooltipProps<number, string> & { groupKeys: string[]; colorByGroup: Record<string, string> }) {
  if (!active || !payload?.length) return null;
  const sorted = [...payload].sort((a, b) => Number(b.value ?? 0) - Number(a.value ?? 0));
  const showSeriesName = groupKeys.length > 1 || (groupKeys[0] && groupKeys[0] !== "All");
  return (
    <div className="rounded-md border border-white/10 bg-black/95 p-3 text-xs text-neutral-100 shadow-lg backdrop-blur">
      <p className="font-mono text-[10px] text-neutral-400">{String(label ?? "")}</p>
      <ul className="mt-1 space-y-0.5">
        {sorted.map((p) => {
          const key = String(p.dataKey);
          const value = p.value;
          if (value === null || value === undefined) return null;
          return (
            <li key={key} className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 rounded-sm"
                style={{ background: colorByGroup[key] ?? "#0ea5e9" }}
              />
              {showSeriesName && <span className="text-neutral-200">{key}:</span>}
              <span className="font-mono text-neutral-100">
                {typeof value === "number" ? value.toLocaleString() : String(value)}
              </span>
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
