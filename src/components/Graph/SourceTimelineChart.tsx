import { useEffect, useMemo, useRef, useState } from "react";
import { Plus, X } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipProps } from "recharts";
import { detectCategoricalFields, detectDateField, detectNumericFields, type DatasetRow } from "../../data/hf/rows";
import type { SourceMetadata } from "../../types/source";

interface Props {
  source: SourceMetadata;
  rows: DatasetRow[];
}

const ALL = "__all__";
const ROW_LEVEL_NON_FILTERS = ["location_id_native", "location_name", "as_of"];

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

  // Categorical filter axes — anything not numeric, not the date, not a row-level
  // traceability column. SEPARATE from the metric (numeric Y-axis).
  const filterFields = useMemo(
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

  const [activeFilters, setActiveFilters] = useState<ActiveFilter[]>([]);

  // First time filterFields arrive, surface a location_id filter if present —
  // but leave it set to All so the chart shows everything by default.
  const initRef = useRef(false);
  useEffect(() => {
    if (initRef.current || filterFields.length === 0) return;
    initRef.current = true;
    if (filterFields.some((f) => f.name === "location_id")) {
      setActiveFilters([{ name: "location_id", value: ALL }]);
    }
  }, [filterFields]);

  // Drop active filters whose underlying field is gone, and reset values that no
  // longer exist.
  useEffect(() => {
    setActiveFilters((curr) => {
      const next = curr
        .filter((f) => filterFields.some((ff) => ff.name === f.name))
        .map((f) => {
          const field = filterFields.find((ff) => ff.name === f.name)!;
          if (f.value === ALL || field.values.includes(f.value)) return f;
          return { ...f, value: ALL };
        });
      return next.length === curr.length && next.every((f, i) => f.value === curr[i].value) ? curr : next;
    });
  }, [filterFields]);

  const availableForAdd = useMemo(
    () => filterFields.filter((f) => !activeFilters.some((af) => af.name === f.name)),
    [filterFields, activeFilters]
  );

  const addFilter = (name: string) => {
    if (!filterFields.some((f) => f.name === name)) return;
    setActiveFilters((curr) => (curr.some((f) => f.name === name) ? curr : [...curr, { name, value: ALL }]));
  };
  const removeFilter = (name: string) =>
    setActiveFilters((curr) => curr.filter((f) => f.name !== name));
  const setFilterValue = (name: string, value: string) =>
    setActiveFilters((curr) => curr.map((f) => (f.name === name ? { ...f, value } : f)));

  // Add-filter popover.
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

  const chartData = useMemo(() => {
    if (!dateField || !metric) return [];
    return rows
      .filter((row) => {
        for (const f of activeFilters) {
          if (f.value === ALL) continue;
          if (String(row[f.name] ?? "") !== f.value) return false;
        }
        return true;
      })
      .map((row) => {
        const rawDate = row[dateField];
        const date = typeof rawDate === "string" ? rawDate.slice(0, 10) : String(rawDate ?? "");
        const rawValue = row[metric];
        const value = typeof rawValue === "number" ? rawValue : Number(rawValue);
        return { date, value: Number.isFinite(value) ? value : null, _row: row };
      })
      .filter((d) => d.date && d.value !== null)
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [rows, dateField, metric, activeFilters]);

  const valueColumnMeta = source.value_columns.find((c) => c.name === metric);

  if (!dateField) return <Empty body="No date column detected on this dataset." />;
  if (numericFields.length === 0) return <Empty body="No numeric metrics declared or detected." />;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start gap-3 text-xs">
        {/* Metric box: Y-axis selector with unit/type on one line below */}
        <div className="flex min-w-[160px] flex-col gap-1 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
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
          {(valueColumnMeta?.unit || valueColumnMeta?.value_type) && (
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-neutral-400">
              {valueColumnMeta.unit && (
                <span>
                  unit: <span className="text-neutral-200">{valueColumnMeta.unit}</span>
                </span>
              )}
              {valueColumnMeta.value_type && (
                <span>
                  type: <span className="text-neutral-200">{valueColumnMeta.value_type}</span>
                </span>
              )}
            </div>
          )}
        </div>

        {/* Filters box: + on the left, active filters spread to the right */}
        {(filterFields.length > 0 || activeFilters.length > 0) && (
          <div className="flex flex-col gap-1 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2">
            <span className="text-[10px] font-semibold uppercase text-neutral-400">Filters</span>
            <div className="flex flex-wrap items-end gap-2">
              <div className="relative" ref={menuRef}>
                <button
                  type="button"
                  onClick={() => setMenuOpen((o) => !o)}
                  disabled={availableForAdd.length === 0}
                  title={availableForAdd.length === 0 ? "All filterable columns are active" : "Add filter"}
                  aria-label="Add filter"
                  aria-haspopup="menu"
                  aria-expanded={menuOpen}
                  className="flex h-7 w-7 items-center justify-center rounded-md border border-white/15 bg-white/[0.04] text-neutral-300 transition hover:border-red-500 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-white/15 disabled:hover:text-neutral-300"
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

              {activeFilters.map((filter) => {
                const field = filterFields.find((f) => f.name === filter.name);
                if (!field) return null;
                return (
                  <div key={filter.name} className="flex min-w-[120px] flex-col gap-0.5">
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
          </div>
        )}
      </div>

      {chartData.length === 0 ? (
        <Empty body="No rows match the current filters." />
      ) : (
        <div className="h-[360px] rounded-lg border border-white/10 bg-white p-3">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
              <CartesianGrid stroke="#e5e5e5" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#525252", fontSize: 12 }} minTickGap={28} stroke="#d4d4d4" />
              <YAxis tick={{ fill: "#525252", fontSize: 12 }} stroke="#d4d4d4" />
              <Tooltip content={<HoverCard metric={metric ?? ""} dateField={dateField} />} />
              <Line type="monotone" dataKey="value" stroke="#b91c1c" strokeWidth={2.4} dot={false} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function HoverCard({
  metric,
  dateField,
  active,
  payload
}: TooltipProps<number, string> & { metric: string; dateField: string }) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload as { _row?: DatasetRow } | undefined;
  const row = point?._row ?? {};
  const entries = Object.entries(row).filter(([k]) => k !== dateField && k !== metric);
  return (
    <div className="rounded-md border border-neutral-300 bg-white p-3 text-xs text-neutral-800 shadow">
      <p className="font-mono text-[10px] text-neutral-500">{String((row as Record<string, unknown>)[dateField] ?? "")}</p>
      <p className="mt-1 text-sm font-semibold">
        {metric}: {String((row as Record<string, unknown>)[metric] ?? "")}
      </p>
      {entries.length > 0 && (
        <dl className="mt-2 grid max-w-xs grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
          {entries.slice(0, 8).flatMap(([k, v]) => [
            <dt key={`${k}-k`} className="font-mono text-[10px] text-neutral-500">
              {k}
            </dt>,
            <dd key={`${k}-v`} className="truncate text-neutral-700">
              {v === null || v === undefined ? "—" : String(v)}
            </dd>
          ])}
        </dl>
      )}
    </div>
  );
}

function Empty({ body }: { body: string }) {
  return <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">{body}</div>;
}
