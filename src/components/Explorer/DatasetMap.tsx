import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Pause, Play } from "lucide-react";
import type { FeatureCollection, Geometry } from "geojson";
import { BoundaryMap, type BoundaryFeatureProps, type BoundarySelection } from "../Map/BoundaryMap";
import { buildCountryBoundariesGeoJson } from "../Map/countrySelectionLayer";
import { iso2ToIso3 } from "../../utils/countryCodes";
import { loadUsCountiesGeoJson, loadUsStatesGeoJson } from "../../data/locations/usAtlas";
import {
  boundaryLabel,
  detectBoundaryLevels,
  isRenderable,
  type BoundaryType,
  type DetectedLevel
} from "../../data/locations/detection";
import { detectDateField, detectNumericFields, type DatasetRow } from "../../data/hf/rows";
import type { SourceMetadata, ValueColumn } from "../../types/source";

interface Props {
  source: SourceMetadata;
  rows: DatasetRow[];
}

// Continental + Alaska/Hawaii bounds. Loose so we don't aggressively crop.
const US_BOUNDS: [[number, number], [number, number]] = [
  [-179, 17],
  [-66, 72]
];

// Columns we never want to surface in the breakdown panel — they identify
// the (location, date) cell, not extra dimensions of the observation.
const ROW_LEVEL_CONVENTION_COLS = new Set([
  "date",
  "location_id",
  "location_level",
  "location_id_native",
  "location_name",
  "as_of"
]);

// Speed → ms per scrubber tick when playing.
const SPEED_OPTIONS: { label: string; ms: number }[] = [
  { label: "1×", ms: 500 },
  { label: "2×", ms: 250 },
  { label: "5×", ms: 100 },
  { label: "10×", ms: 50 }
];

export function DatasetMap({ source, rows }: Props) {
  const levels = useMemo(() => detectBoundaryLevels(rows), [rows]);
  const renderableLevels = useMemo(() => levels.filter((l) => isRenderable(l.boundaryType)), [levels]);

  const [chosenKey, setChosenKey] = useState<string | null>(null);

  useEffect(() => {
    if (chosenKey === null && renderableLevels.length > 0) {
      setChosenKey(levelKey(renderableLevels[0]));
    } else if (chosenKey !== null && !renderableLevels.some((l) => levelKey(l) === chosenKey)) {
      setChosenKey(renderableLevels[0] ? levelKey(renderableLevels[0]) : null);
    }
  }, [renderableLevels, chosenKey]);

  const chosenLevel = renderableLevels.find((l) => levelKey(l) === chosenKey) ?? null;

  if (levels.length === 0) {
    return (
      <div className="rounded-md border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
        No location data detected.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {(renderableLevels.length > 1 || levels.some((l) => !isRenderable(l.boundaryType))) && (
        <LevelSelector levels={levels} chosenKey={chosenKey} onChange={setChosenKey} />
      )}

      {chosenLevel ? (
        <RenderedMap level={chosenLevel} source={source} rows={rows} />
      ) : (
        <UnsupportedNote levels={levels} />
      )}
    </div>
  );
}

function levelKey(l: DetectedLevel): string {
  return `${l.level}::${l.boundaryType}`;
}

interface LevelSelectorProps {
  levels: DetectedLevel[];
  chosenKey: string | null;
  onChange: (key: string) => void;
}

function LevelSelector({ levels, chosenKey, onChange }: LevelSelectorProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
      <span className="text-[10px] font-semibold uppercase text-neutral-400">Map level</span>
      <div className="flex flex-wrap gap-1">
        {levels.map((l) => {
          const key = levelKey(l);
          const renderable = isRenderable(l.boundaryType);
          const active = chosenKey === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => renderable && onChange(key)}
              disabled={!renderable}
              title={
                renderable
                  ? `${l.rowCount.toLocaleString()} rows · ${l.ids.size.toLocaleString()} unique ids`
                  : `${boundaryLabel(l.boundaryType)} — sample: ${l.unmatchedSamples.slice(0, 2).join(", ") || "—"}`
              }
              className={`rounded-md border px-2 py-0.5 text-[11px] transition ${
                active
                  ? "border-red-500/60 bg-red-700/40 text-red-100"
                  : renderable
                  ? "border-white/15 bg-white/[0.04] text-neutral-200 hover:border-red-500 hover:text-red-200"
                  : "border-white/10 bg-white/[0.02] text-neutral-500 cursor-not-allowed"
              }`}
            >
              <span>{l.level}</span>
              <span className="ml-1 text-[10px] opacity-70">{boundaryLabelShort(l.boundaryType)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function boundaryLabelShort(t: BoundaryType): string {
  switch (t) {
    case "country":
      return "country";
    case "us-state":
      return "US state";
    case "us-county":
      return "US county";
    case "iso3166-2":
      return "subnational (not yet)";
    case "subnational-region":
      return "ad-hoc region";
    case "point":
      return "point (not yet)";
    case "facility":
      return "facility (not yet)";
    default:
      return "unsupported";
  }
}

interface RenderedMapProps {
  level: DetectedLevel;
  source: SourceMetadata;
  rows: DatasetRow[];
}

function RenderedMap({ level, source, rows }: RenderedMapProps) {
  const country = useCountryView(level, source);
  const usState = useUsBoundaryView(level, "us-state");
  const usCounty = useUsBoundaryView(level, "us-county");
  const view = level.boundaryType === "country" ? country : level.boundaryType === "us-state" ? usState : usCounty;

  const [selected, setSelected] = useState<BoundarySelection | null>(null);
  useEffect(() => {
    setSelected(null);
  }, [level.boundaryType, level.level]);

  const dateField = useMemo(() => detectDateField(rows), [rows]);

  const declaredNumeric = source.value_columns
    .filter((c) => c.dtype === "int" || c.dtype === "float")
    .map((c) => c.name);
  const detectedNumeric = useMemo(
    () => detectNumericFields(rows, [dateField ?? "", "location_id_native", "location_name", "as_of"]),
    [rows, dateField]
  );
  const numericFields = declaredNumeric.length > 0 ? declaredNumeric : detectedNumeric;

  const [metric, setMetric] = useState<string | null>(null);
  useEffect(() => {
    if (metric === null && numericFields.length > 0) setMetric(numericFields[0]);
    else if (metric !== null && !numericFields.includes(metric)) setMetric(numericFields[0] ?? null);
  }, [metric, numericFields]);

  const valueColumnMeta = source.value_columns.find((c) => c.name === metric);
  const aggMethod = pickAggregation(valueColumnMeta);

  // Bucket rows: date → boundaryId → aggregated value.
  const { valueByDateAndId, dates } = useMemo(() => {
    const result = { valueByDateAndId: new Map<string, Map<string, number>>(), dates: [] as string[] };
    if (!dateField || !metric || !view) return result;

    const buckets = new Map<string, Map<string, number[]>>();
    for (const row of rows) {
      const dateRaw = row[dateField];
      const date = typeof dateRaw === "string" ? dateRaw.slice(0, 10) : String(dateRaw ?? "");
      if (!date) continue;
      const id = rowToBoundaryId(row, level.boundaryType);
      if (!id) continue;
      const valueRaw = row[metric];
      const value = typeof valueRaw === "number" ? valueRaw : Number(valueRaw);
      if (!Number.isFinite(value)) continue;

      let g = buckets.get(date);
      if (!g) {
        g = new Map();
        buckets.set(date, g);
      }
      let arr = g.get(id);
      if (!arr) {
        arr = [];
        g.set(id, arr);
      }
      arr.push(value);
    }

    const valueByDateAndId = new Map<string, Map<string, number>>();
    for (const [date, idMap] of buckets) {
      const out = new Map<string, number>();
      for (const [id, values] of idMap) out.set(id, aggregate(values, aggMethod));
      valueByDateAndId.set(date, out);
    }
    const dates = Array.from(valueByDateAndId.keys()).sort();
    return { valueByDateAndId, dates };
  }, [rows, dateField, metric, view, level.boundaryType, aggMethod]);

  // Stable color scale across time: p99 of all aggregated values.
  const vmax = useMemo(() => {
    const all: number[] = [];
    for (const idMap of valueByDateAndId.values()) {
      for (const v of idMap.values()) if (Number.isFinite(v)) all.push(v);
    }
    if (all.length === 0) return 1;
    all.sort((a, b) => a - b);
    const p99 = all[Math.floor(all.length * 0.99)] ?? all[all.length - 1];
    return Math.max(p99, 1e-9);
  }, [valueByDateAndId]);

  // Range trim + playhead. We initialize trim to full range and playhead to
  // start the *first* time dates appears. After that, we preserve whatever
  // the user has set — re-running the metric/level effect must not yank
  // the playhead to the end of the bar (which it used to do).
  const [startIdx, setStartIdx] = useState(0);
  const [endIdx, setEndIdx] = useState(0);
  const [dateIdx, setDateIdx] = useState(0);
  const initialisedRef = useRef(false);

  useEffect(() => {
    if (dates.length === 0) {
      setStartIdx(0);
      setEndIdx(0);
      setDateIdx(0);
      initialisedRef.current = false;
      return;
    }
    if (!initialisedRef.current) {
      initialisedRef.current = true;
      setStartIdx(0);
      setEndIdx(dates.length - 1);
      setDateIdx(0);
      return;
    }
    // Subsequent dates change — clamp without resetting. If a saved index
    // is out of range under the new dates list, fall back to the start.
    setStartIdx((c) => Math.min(c, dates.length - 1));
    setEndIdx((c) => Math.min(c, dates.length - 1));
    setDateIdx((c) => (c >= 0 && c < dates.length ? c : 0));
  }, [dates]);

  // Clamp playhead to the trimmed window.
  useEffect(() => {
    if (dates.length === 0) return;
    setDateIdx((curr) => Math.min(Math.max(curr, startIdx), endIdx));
  }, [startIdx, endIdx, dates.length]);

  const currentDate = dates[dateIdx] ?? null;

  const valueByLocation = useMemo(() => {
    if (!currentDate) return undefined;
    const raw = valueByDateAndId.get(currentDate);
    if (!raw) return new Map<string, number>();
    const out = new Map<string, number>();
    for (const [id, v] of raw) out.set(id, Math.min(Math.max(v / vmax, 0), 1));
    return out;
  }, [valueByDateAndId, currentDate, vmax]);

  const selectedAggregateValue =
    selected && currentDate ? valueByDateAndId.get(currentDate)?.get(selected.id) ?? null : null;

  // Underlying source rows for the selected (region, date). Used to populate
  // the breakdown — the *individual* observations whose aggregate is the big
  // number. Empty when nothing is selected.
  const selectedBreakdownRows = useMemo(() => {
    if (!selected || !currentDate || !dateField) return [];
    return rows.filter((r) => {
      const id = rowToBoundaryId(r, level.boundaryType);
      if (id !== selected.id) return false;
      const dRaw = r[dateField];
      const d = typeof dRaw === "string" ? dRaw.slice(0, 10) : String(dRaw ?? "");
      return d === currentDate;
    });
  }, [selected, currentDate, dateField, rows, level.boundaryType]);

  // Play / pause.
  const [isPlaying, setIsPlaying] = useState(false);
  const [speedMs, setSpeedMs] = useState(SPEED_OPTIONS[1].ms);
  useEffect(() => {
    if (!isPlaying || dates.length <= 1) return;
    const id = window.setInterval(() => {
      setDateIdx((curr) => {
        const next = curr + 1;
        if (next > endIdx) {
          setIsPlaying(false);
          return curr;
        }
        return next;
      });
    }, speedMs);
    return () => window.clearInterval(id);
  }, [isPlaying, speedMs, dates.length, endIdx]);

  if (!view) {
    return (
      <div className="rounded-md border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
        Loading boundaries…
      </div>
    );
  }

  const usBased = level.boundaryType === "us-state" || level.boundaryType === "us-county";
  const missingCount = view.scopeIds ? Math.max(0, view.scopeIds.size - view.highlightedIds.size) : 0;
  const scrubberActive = !!metric && dates.length > 0;
  const reportingCount = scrubberActive && currentDate ? valueByDateAndId.get(currentDate)?.size ?? 0 : 0;
  const aggLabel = aggregationLabel(aggMethod, valueColumnMeta?.aggregation);

  return (
    <>
      {numericFields.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
          <span className="text-[10px] font-semibold uppercase text-neutral-400">Metric</span>
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
          {valueColumnMeta?.unit && (
            <span className="text-[10px] text-neutral-400">
              unit: <span className="text-neutral-200">{valueColumnMeta.unit}</span>
            </span>
          )}
          <span className="text-[10px] text-neutral-400">
            agg: <span className="text-neutral-200">{aggLabel}</span>
          </span>
          {scrubberActive && (
            <ColorRamp vmax={vmax} unit={valueColumnMeta?.unit} />
          )}
        </div>
      )}

      <div className="h-[520px]">
        <BoundaryMap
          geojson={view.geojson}
          highlightedIds={view.highlightedIds}
          scopeIds={view.scopeIds}
          valueByLocation={scrubberActive ? valueByLocation : undefined}
          selected={selected}
          onSelect={setSelected}
          initialBounds={usBased ? US_BOUNDS : undefined}
        />
      </div>

      {scrubberActive && (
        <Scrubber
          dates={dates}
          startIdx={startIdx}
          endIdx={endIdx}
          onStartIdx={setStartIdx}
          onEndIdx={setEndIdx}
          dateIdx={dateIdx}
          onDateIdx={setDateIdx}
          isPlaying={isPlaying}
          onTogglePlay={() => setIsPlaying((p) => !p)}
          speedMs={speedMs}
          onSpeedMs={setSpeedMs}
        />
      )}

      <InfoPanel
        currentDate={currentDate}
        scrubberActive={scrubberActive}
        reportingCount={reportingCount}
        coverageBaseline={view.highlightedIds.size}
        missingCount={missingCount}
        selected={selected}
        selectedAggregateValue={selectedAggregateValue}
        breakdownRows={selectedBreakdownRows}
        metric={metric}
        unit={valueColumnMeta?.unit}
        aggregationLabelText={aggLabel}
      />
    </>
  );
}

interface InfoPanelProps {
  currentDate: string | null;
  scrubberActive: boolean;
  reportingCount: number;
  coverageBaseline: number;
  missingCount: number;
  selected: BoundarySelection | null;
  selectedAggregateValue: number | null;
  breakdownRows: DatasetRow[];
  metric: string | null;
  unit?: string;
  aggregationLabelText: string;
}

function InfoPanel({
  currentDate,
  scrubberActive,
  reportingCount,
  coverageBaseline,
  missingCount,
  selected,
  selectedAggregateValue,
  breakdownRows,
  metric,
  unit,
  aggregationLabelText
}: InfoPanelProps) {
  return (
    <div className="rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-neutral-300">
        {scrubberActive && currentDate ? (
          <>
            <span className="font-mono text-sm text-white">{currentDate}</span>
            <span className="text-[11px] text-neutral-400">
              <span className="inline-block h-2 w-2 rounded-sm align-middle" style={{ background: "rgba(220,38,38,0.42)" }} />{" "}
              {reportingCount.toLocaleString()} reporting
            </span>
          </>
        ) : (
          <span className="text-[11px] text-neutral-400">
            <span className="inline-block h-2 w-2 rounded-sm align-middle" style={{ background: "rgba(220,38,38,0.42)" }} />{" "}
            {coverageBaseline.toLocaleString()} with data
          </span>
        )}
        {missingCount > 0 && (
          <span className="text-[11px] text-neutral-400">
            <span className="inline-block h-2 w-2 rounded-sm align-middle" style={{ background: "rgba(255,255,255,0.18)" }} />{" "}
            {missingCount.toLocaleString()} in scope, no data
          </span>
        )}
      </div>

      {selected ? (
        <div className="mt-3">
          <div className="flex items-baseline gap-2 text-neutral-300">
            <span className="text-sm font-medium text-white">
              {selected.name || <span className="text-neutral-400">(unnamed)</span>}
            </span>
            <span className="font-mono text-[10px] text-neutral-500">{selected.id}</span>
          </div>
          {scrubberActive && (
            <div className="mt-1">
              {selectedAggregateValue !== null && Number.isFinite(selectedAggregateValue) ? (
                <>
                  <p className="text-3xl font-semibold leading-tight text-white">
                    {formatNumber(selectedAggregateValue)}
                  </p>
                  <p className="mt-0.5 text-[11px] text-neutral-400">
                    {metric ?? "value"}
                    {unit ? ` · ${unit}` : ""}
                    {breakdownRows.length > 1 && ` · ${aggregationLabelText} of ${breakdownRows.length} rows`}
                  </p>
                </>
              ) : (
                <p className="text-sm text-neutral-400">no observation on {currentDate}</p>
              )}
            </div>
          )}
          {breakdownRows.length > 0 && metric && (
            <Breakdown rows={breakdownRows} metric={metric} unit={unit} />
          )}
        </div>
      ) : (
        <p className="mt-2 text-neutral-400">Click a region on the map to inspect.</p>
      )}
    </div>
  );
}

interface BreakdownProps {
  rows: DatasetRow[];
  metric: string;
  unit?: string;
}

function Breakdown({ rows, metric, unit }: BreakdownProps) {
  // Find the dimension columns — keys that vary across the rows AND aren't
  // row-level convention or the metric itself. If no dimensions vary, the
  // breakdown is just one row, which we don't bother rendering since the
  // headline value already says it.
  const dimensionKeys = useMemo(() => {
    if (rows.length <= 1) return [];
    const keys = new Set<string>();
    for (const r of rows) for (const k of Object.keys(r)) keys.add(k);
    const out: string[] = [];
    for (const k of keys) {
      if (k === metric) continue;
      if (ROW_LEVEL_CONVENTION_COLS.has(k)) continue;
      const seen = new Set<string>();
      for (const r of rows) {
        const v = r[k];
        seen.add(v === null || v === undefined ? "" : String(v));
        if (seen.size > 1) break;
      }
      if (seen.size > 1) out.push(k);
    }
    return out;
  }, [rows, metric]);

  if (dimensionKeys.length === 0) return null;

  // Sort rows descending by metric value for legibility.
  const ordered = [...rows].sort((a, b) => {
    const av = Number(a[metric]);
    const bv = Number(b[metric]);
    if (!Number.isFinite(av)) return 1;
    if (!Number.isFinite(bv)) return -1;
    return bv - av;
  });

  return (
    <div className="mt-3">
      <p className="text-[10px] font-semibold uppercase text-neutral-400">Breakdown</p>
      {/* auto-cols keep the value flush against the label so we don't get
          a label on the far left and a value on the far right of a wide pane. */}
      <dl className="mt-1 grid grid-cols-[max-content_max-content] gap-x-4 gap-y-1 text-sm">
        {ordered.map((r, i) => {
          const key = dimensionKeys.map((k) => formatCellShort(r[k])).join(" · ");
          const v = Number(r[metric]);
          return (
            <div key={i} className="contents">
              <dt className="truncate text-neutral-300">{key || "(no dimensions)"}</dt>
              <dd className="font-mono text-white">
                {Number.isFinite(v) ? formatNumber(v) : "—"}
                {unit && <span className="ml-1 text-[11px] text-neutral-500">{unit}</span>}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}

interface ColorRampProps {
  vmax: number;
  unit?: string;
}

function ColorRamp({ vmax, unit }: ColorRampProps) {
  return (
    <div className="flex items-center gap-2 text-[10px] text-neutral-400" title="99th-percentile cap so outliers don't crush the scale">
      <span>color</span>
      <span className="text-neutral-300">0</span>
      <span
        className="block h-2 w-24 rounded-sm"
        style={{ background: "linear-gradient(to right, rgba(220,38,38,0.10), rgba(220,38,38,0.85))" }}
        aria-hidden="true"
      />
      <span className="text-neutral-300">
        {formatNumber(vmax)}+ {unit && <span className="text-neutral-500">{unit}</span>}
      </span>
    </div>
  );
}

interface ScrubberProps {
  dates: string[];
  startIdx: number;
  endIdx: number;
  onStartIdx: (n: number) => void;
  onEndIdx: (n: number) => void;
  dateIdx: number;
  onDateIdx: (n: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  speedMs: number;
  onSpeedMs: (n: number) => void;
}

function Scrubber({
  dates,
  startIdx,
  endIdx,
  onStartIdx,
  onEndIdx,
  dateIdx,
  onDateIdx,
  isPlaying,
  onTogglePlay,
  speedMs,
  onSpeedMs
}: ScrubberProps) {
  const safeIdx = Math.max(startIdx, Math.min(dateIdx, endIdx));
  const currentDate = dates[safeIdx] ?? "";
  const atEnd = safeIdx >= endIdx;

  return (
    <div className="space-y-2 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
      <TimelineBar
        dates={dates}
        startIdx={startIdx}
        endIdx={endIdx}
        playheadIdx={safeIdx}
        onStartIdx={(v) => onStartIdx(Math.max(0, Math.min(v, endIdx)))}
        onEndIdx={(v) => onEndIdx(Math.min(dates.length - 1, Math.max(v, startIdx)))}
        onPlayheadIdx={(v) => onDateIdx(Math.max(startIdx, Math.min(v, endIdx)))}
      />

      <div className="flex flex-wrap items-center gap-2">
        <DateInput
          dates={dates}
          value={dates[startIdx] ?? ""}
          onChangeIdx={(v) => onStartIdx(Math.max(0, Math.min(v, endIdx)))}
          label="From"
        />
        <DateInput
          dates={dates}
          value={dates[endIdx] ?? ""}
          onChangeIdx={(v) => onEndIdx(Math.min(dates.length - 1, Math.max(v, startIdx)))}
          label="To"
        />

        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => onDateIdx(Math.max(startIdx, safeIdx - 1))}
            disabled={safeIdx <= startIdx}
            className="rounded border border-white/10 p-1 text-neutral-200 transition hover:border-red-500 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Previous date"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={onTogglePlay}
            disabled={atEnd && !isPlaying}
            className="rounded border border-white/10 p-1 text-neutral-200 transition hover:border-red-500 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label={isPlaying ? "Pause" : "Play"}
            title={atEnd && !isPlaying ? "At end — step back to play again" : undefined}
          >
            {isPlaying ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          </button>
          <button
            type="button"
            onClick={() => onDateIdx(Math.min(endIdx, safeIdx + 1))}
            disabled={atEnd}
            className="rounded border border-white/10 p-1 text-neutral-200 transition hover:border-red-500 hover:text-red-200 disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Next date"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
          <span className="ml-1 w-[88px] text-right font-mono text-[11px] text-neutral-200">{currentDate}</span>
          <select
            value={speedMs}
            onChange={(e) => onSpeedMs(Number(e.target.value))}
            className="rounded-md border border-white/10 bg-black/60 px-1.5 py-0.5 text-[11px] text-white"
            aria-label="Playback speed"
          >
            {SPEED_OPTIONS.map((o) => (
              <option key={o.ms} value={o.ms}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
}

interface TimelineBarProps {
  dates: string[];
  startIdx: number;
  endIdx: number;
  playheadIdx: number;
  onStartIdx: (v: number) => void;
  onEndIdx: (v: number) => void;
  onPlayheadIdx: (v: number) => void;
}

// One bar with three handles: two trim thumbs at the ends and a playhead
// in between. The playhead input is positioned to span only the active band
// — when you trim inward, the playhead's draggable surface physically
// shrinks, like iPhone's video trim. DOM order matters here: the playhead
// is rendered first so the trim thumbs stack on top and never get hidden
// by the playhead's larger hit area.
function TimelineBar({ dates, startIdx, endIdx, playheadIdx, onStartIdx, onEndIdx, onPlayheadIdx }: TimelineBarProps) {
  const max = Math.max(0, dates.length - 1);
  const pct = (i: number) => (max === 0 ? 0 : (i / max) * 100);
  const startPct = pct(startIdx);
  const endPct = pct(endIdx);
  const trimWidth = Math.max(endPct - startPct, 0);
  const trimDegenerate = endIdx <= startIdx;

  return (
    <div className="relative h-7 px-1">
      {/* Background track — full date range. */}
      <div className="absolute left-1 right-1 top-1/2 h-1 -translate-y-1/2 rounded-full bg-white/[0.10]" />
      {/* Active band — between the trim handles. */}
      <div
        className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-red-500/40"
        style={{ left: `calc(${startPct}% + 4px)`, width: `calc(${trimWidth}% - 0px)` }}
      />

      {/* Playhead — positioned to span ONLY the active band so it can't
          travel outside it. Lower in DOM order than trim inputs so the
          trim thumbs stay clickable in the overlap regions. */}
      {!trimDegenerate && (
        <div
          className="absolute top-0 h-7"
          style={{
            left: `calc(${startPct}% + 4px)`,
            width: `calc(${trimWidth}% - 0px)`
          }}
        >
          <input
            type="range"
            min={startIdx}
            max={endIdx}
            value={Math.max(startIdx, Math.min(playheadIdx, endIdx))}
            onChange={(e) => onPlayheadIdx(Number(e.target.value))}
            className="playhead-range absolute inset-0 w-full"
            aria-label="Date playhead"
          />
        </div>
      )}

      {/* Trim handles — full-width inputs with invisible tracks (pointer-
          events: none) and visible interactive thumbs. */}
      <input
        type="range"
        min={0}
        max={max}
        value={startIdx}
        onChange={(e) => onStartIdx(Number(e.target.value))}
        className="dual-range-input absolute inset-x-0 top-1/2 w-full -translate-y-1/2"
        aria-label="Range start"
      />
      <input
        type="range"
        min={0}
        max={max}
        value={endIdx}
        onChange={(e) => onEndIdx(Number(e.target.value))}
        className="dual-range-input absolute inset-x-0 top-1/2 w-full -translate-y-1/2"
        aria-label="Range end"
      />
    </div>
  );
}

interface DateInputProps {
  dates: string[];
  value: string;
  label: string;
  onChangeIdx: (idx: number) => void;
}

function DateInput({ dates, value, label, onChangeIdx }: DateInputProps) {
  const handleChange = (raw: string) => {
    if (!raw) return;
    const idx = findNearestDateIdx(raw, dates);
    if (idx >= 0) onChangeIdx(idx);
  };
  return (
    <label className="flex items-center gap-1 text-[10px] text-neutral-400">
      <span>{label}</span>
      <input
        type="date"
        value={value}
        min={dates[0]}
        max={dates[dates.length - 1]}
        onChange={(e) => handleChange(e.target.value)}
        className="rounded-md border border-white/10 bg-black/60 px-1.5 py-0.5 text-[11px] font-mono text-white [color-scheme:dark]"
      />
    </label>
  );
}

function findNearestDateIdx(target: string, dates: string[]): number {
  if (dates.length === 0) return -1;
  // Quick exact match.
  const exact = dates.indexOf(target);
  if (exact >= 0) return exact;
  // Else linear nearest by string compare (works for YYYY-MM-DD).
  let best = 0;
  let bestDiff = Math.abs(dateMillis(target) - dateMillis(dates[0]));
  for (let i = 1; i < dates.length; i++) {
    const diff = Math.abs(dateMillis(target) - dateMillis(dates[i]));
    if (diff < bestDiff) {
      best = i;
      bestDiff = diff;
    }
  }
  return best;
}

function dateMillis(yyyymmdd: string): number {
  const t = Date.parse(yyyymmdd);
  return Number.isNaN(t) ? 0 : t;
}

type AggregationMethod = "sum" | "mean" | "max" | "min" | "count";

function pickAggregation(meta: ValueColumn | undefined): AggregationMethod {
  switch (meta?.aggregation) {
    case "sum":
    case "count":
      return "sum";
    case "max":
      return "max";
    case "mean":
    case "rate":
    case "proportion":
      return "mean";
    case "none":
    default:
      return "mean";
  }
}

function aggregate(values: number[], method: AggregationMethod): number {
  if (values.length === 0) return NaN;
  switch (method) {
    case "sum":
      return values.reduce((a, b) => a + b, 0);
    case "max":
      return values.reduce((a, b) => (b > a ? b : a), -Infinity);
    case "min":
      return values.reduce((a, b) => (b < a ? b : a), Infinity);
    case "count":
      return values.length;
    case "mean":
    default:
      return values.reduce((a, b) => a + b, 0) / values.length;
  }
}

function aggregationLabel(method: AggregationMethod, declared: ValueColumn["aggregation"] | undefined): string {
  if (declared && declared !== "none") return declared;
  return method === "sum" ? "sum" : "mean";
}

function rowToBoundaryId(row: DatasetRow, boundaryType: BoundaryType): string | null {
  const v = row.location_id;
  if (typeof v !== "string") return null;
  switch (boundaryType) {
    case "country":
      return iso2ToIso3(v.toUpperCase());
    case "us-state":
    case "us-county":
      return v;
    default:
      return null;
  }
}

function formatNumber(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (Math.abs(v) >= 1) return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

function formatCellShort(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return Number.isFinite(v) ? v.toLocaleString() : String(v);
  return String(v);
}

interface BoundaryView {
  geojson: FeatureCollection<Geometry, BoundaryFeatureProps>;
  highlightedIds: ReadonlySet<string>;
  scopeIds?: ReadonlySet<string>;
}

function useCountryView(level: DetectedLevel, source: SourceMetadata): BoundaryView | null {
  return useMemo(() => {
    if (level.boundaryType !== "country") return null;
    const base = buildCountryBoundariesGeoJson();
    const reshaped: FeatureCollection<Geometry, BoundaryFeatureProps> = {
      type: "FeatureCollection",
      features: base.features.map((f) => ({
        ...f,
        properties: { id: f.properties.iso3, name: f.properties.name }
      }))
    };
    const iso3Ids = new Set<string>();
    for (const iso2 of level.ids) {
      const iso3 = iso2ToIso3(iso2);
      if (iso3) iso3Ids.add(iso3);
    }
    let scopeIds: Set<string> | undefined;
    const declared = source.geography_countries;
    if (declared.length > 0 && !declared.includes("multiple")) {
      scopeIds = new Set();
      for (const c of declared) {
        const iso3 = iso2ToIso3(c);
        if (iso3) scopeIds.add(iso3);
      }
    }
    return { geojson: reshaped, highlightedIds: iso3Ids, scopeIds };
  }, [level, source]);
}

function useUsBoundaryView(level: DetectedLevel, expectedType: BoundaryType): BoundaryView | null {
  const [view, setView] = useState<BoundaryView | null>(null);
  useEffect(() => {
    if (level.boundaryType !== expectedType) {
      setView(null);
      return;
    }
    let cancelled = false;
    const loader = expectedType === "us-state" ? loadUsStatesGeoJson : loadUsCountiesGeoJson;
    loader().then((geojson) => {
      if (cancelled) return;
      const scopeIds = new Set<string>();
      for (const f of geojson.features) scopeIds.add(f.properties.id);
      setView({ geojson, highlightedIds: level.ids, scopeIds });
    });
    return () => {
      cancelled = true;
    };
  }, [level, expectedType]);
  return view;
}

interface UnsupportedNoteProps {
  levels: DetectedLevel[];
}

function UnsupportedNote({ levels }: UnsupportedNoteProps) {
  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-700/10 p-3 text-xs text-amber-100">
      <p className="font-semibold">No renderable boundaries for this dataset yet.</p>
      <ul className="mt-2 space-y-1 text-amber-100/80">
        {levels.map((l) => (
          <li key={levelKey(l)}>
            <span className="font-mono">{l.level || "(no level)"}</span> — {boundaryLabel(l.boundaryType)}
            {l.unmatchedSamples.length > 0 && (
              <span className="ml-1 text-amber-100/60">(sample: {l.unmatchedSamples.slice(0, 2).join(", ")})</span>
            )}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-amber-100/70">
        We currently render polygons for ISO 3166-1 countries, US states (2-digit FIPS), and US counties (5-digit FIPS).
        Other levels (ISO 3166-2 subnational, points, facilities) will be added later.
      </p>
    </div>
  );
}
