import type { ComponentType, SVGProps } from "react";
import { useEffect, useMemo, useState } from "react";
import { ExternalLink, Eye, EyeOff, Globe2, LineChart, Loader2, RefreshCw, Table2 } from "lucide-react";
import { useDashboard } from "../../state/DashboardContext";
import { useWorkspace, type ExplorerPane } from "../../state/WorkspaceContext";
import { useDatasetSlice } from "../../data/hf/hooks";
import {
  ALL_FILTER,
  SourceTimelineChart,
  predictionColorFor,
  type ActiveFilter
} from "../Graph/SourceTimelineChart";
import { DatasetMap } from "./DatasetMap";
import { DataTable } from "../Graph/DataTable";
import { usePredictionsForTarget } from "../../data/predictions/usePredictions";
import {
  aggregateTruthForScoring,
  computeSubmitterScores,
  dominantPredictionDimValues,
  type SubmitterScore
} from "../../data/predictions/leaderboard";
import { detectDateField } from "../../data/hf/rows";

interface Props {
  pane: ExplorerPane;
}

export function ExplorerBody({ pane }: Props) {
  const { catalog } = useDashboard();
  const { updatePane } = useWorkspace();
  const source = catalog.data?.find((s) => s.id === pane.sourceId) ?? null;
  const slice = useDatasetSlice(pane.sourceId);

  // Chart controls live here (lifted from SourceTimelineChart) so the
  // leaderboard can score against the same filtered/aggregated truth the
  // chart shows, and so we can pin the metric to predictions' target_column.
  // The chart proposes a default metric on mount via the onMetricChange
  // callback; we accept whatever it proposes unless predictions are pinning.
  const [metric, setMetric] = useState<string | null>(null);
  const [activeFilters, setActiveFilters] = useState<ActiveFilter[]>([]);

  // Predictions overlay (v2.5) — fetched lazily from the companion repo.
  // Off by default; enabling fetches and shows accepted forecasts from
  // every submitter unless filtered down via the chip selector below.
  const [predictionsOn, setPredictionsOn] = useState(false);
  // null = "all selected" (default); a Set means the user has explicitly
  // toggled. Re-derived when the submitter list changes.
  const [selectedSubmitters, setSelectedSubmitters] = useState<Set<string> | null>(null);
  const sourceIdForPredictions = predictionsOn ? pane.sourceId : null;
  const sourceIdSlug = pane.sourceId.includes("/") ? pane.sourceId.split("/").pop() ?? pane.sourceId : pane.sourceId;
  const predictions = usePredictionsForTarget(predictionsOn ? sourceIdSlug : null);
  // Toggling off resets selection so re-enabling defaults to "all" again.
  useEffect(() => {
    if (!predictionsOn) setSelectedSubmitters(null);
  }, [predictionsOn]);

  // Pin metric to predictions' target_column whenever the overlay is on
  // and we know what column they target. Otherwise the leaderboard would
  // score against a column the predictions don't even target. The Metric
  // select is disabled in this state (the chart shows a tooltip).
  useEffect(() => {
    if (!predictionsOn) return;
    const target = predictions.parsed?.targetColumn;
    if (target && metric !== target) setMetric(target);
  }, [predictionsOn, predictions.parsed?.targetColumn, metric]);

  const submitterNames = useMemo(
    () => predictions.parsed?.submitters.map((s) => s.submitter) ?? [],
    [predictions.parsed]
  );
  const colorBySubmitter = useMemo(
    () => predictionColorFor(submitterNames),
    [submitterNames]
  );
  const effectiveSelectedSet = useMemo(() => {
    if (!predictionsOn) return new Set<string>();
    return selectedSubmitters ?? new Set(submitterNames);
  }, [predictionsOn, selectedSubmitters, submitterNames]);

  const setTab = (tab: "graph" | "map") =>
    updatePane(pane.id, (p) => (p.type === "explorer" ? { ...p, tab } : p));
  const setShowTable = (showTable: boolean) =>
    updatePane(pane.id, (p) => (p.type === "explorer" ? { ...p, showTable } : p));
  const togglePredictions = () => setPredictionsOn((on) => !on);
  const toggleSubmitter = (submitter: string) =>
    setSelectedSubmitters((curr) => {
      const base = curr ?? new Set(submitterNames);
      const next = new Set(base);
      if (next.has(submitter)) next.delete(submitter);
      else next.add(submitter);
      return next;
    });
  // Suppress unused variable warning for sourceIdForPredictions (kept for future
  // explicit display, e.g. showing the companion repo id in the panel).
  void sourceIdForPredictions;

  // Effective truth filters used for leaderboard scoring. We use the
  // chart's active filters (precise, by column name) — same as what's
  // visible on the chart. This keeps "what's plotted" and "what's
  // scored" in sync.
  const truthFiltersForScoring = useMemo(
    () => activeFilters.filter((f) => f.value !== ALL_FILTER),
    [activeFilters]
  );

  // Per-submitter leaderboard scores. Computed only when we have both
  // predictions and truth. Truth is scoped to the chart's current
  // filters, then aggregated using the predictions' canonical
  // target_column with the column's declared aggregation method.
  const leaderboard: SubmitterScore[] = useMemo(() => {
    if (!predictionsOn || !predictions.parsed || predictions.parsed.rows.length === 0) {
      return [];
    }
    if (slice.status !== "ready" || !slice.data) return [];
    const targetColumn = predictions.parsed.targetColumn;
    if (!targetColumn) return [];
    const truthDateField = detectDateField(slice.data.rows);
    if (!truthDateField) return [];
    const valueCol = source?.value_columns.find((c) => c.name === targetColumn);
    const method =
      valueCol?.aggregation === "sum" ? "sum" : ("mean" as "mean" | "sum");
    const truthByDate = aggregateTruthForScoring(
      slice.data.rows,
      truthDateField,
      targetColumn,
      { filters: truthFiltersForScoring, method }
    );
    return computeSubmitterScores(predictions.parsed, truthByDate);
  }, [predictionsOn, predictions.parsed, slice.status, slice.data, source, truthFiltersForScoring]);

  // Scope-mismatch hint: when predictions consistently target a particular
  // dim value (e.g. location_name=CA from our synth) but the user hasn't
  // applied a matching truth filter, scores will be against a wider truth
  // slice than the predictions cover — usually misleading. Surface a
  // small nudge.
  const scopeHint: { dimValue: string } | null = useMemo(() => {
    if (!predictionsOn || !predictions.parsed) return null;
    const dominant = dominantPredictionDimValues(predictions.parsed);
    if (dominant.length === 0) return null;
    const filterValues = activeFilters
      .filter((f) => f.value !== ALL_FILTER)
      .map((f) => f.value);
    const allCovered = dominant.every((d) => filterValues.includes(d));
    if (allCovered) return null;
    return { dimValue: dominant[0] };
  }, [predictionsOn, predictions.parsed, activeFilters]);

  if (!source) {
    return (
      <div className="p-3 text-sm text-neutral-300">
        {catalog.status === "loading"
          ? "Loading catalog…"
          : `Dataset ${pane.sourceId} not found in the EPI-Eval catalog.`}
      </div>
    );
  }

  return (
    <div className="space-y-3 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.02] p-1">
          <TabButton active={pane.tab === "graph"} onClick={() => setTab("graph")} icon={LineChart} label="Graph" />
          <TabButton active={pane.tab === "map"} onClick={() => setTab("map")} icon={Globe2} label="Map" />
        </div>
        {pane.tab === "graph" && (
          <button
            type="button"
            onClick={togglePredictions}
            aria-pressed={predictionsOn}
            title={
              predictionsOn
                ? "Hide community forecasts overlay"
                : "Show community forecasts from EPI-Eval/" + sourceIdSlug + "-predictions"
            }
            className={`flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold transition ${
              predictionsOn
                ? "border-amber-400/60 bg-amber-500/15 text-amber-100 hover:border-amber-300"
                : "border-white/10 text-neutral-300 hover:border-amber-500/40 hover:text-amber-100"
            }`}
          >
            {predictionsOn ? <Eye className="h-3.5 w-3.5" /> : <EyeOff className="h-3.5 w-3.5" />}
            Predictions
            {predictionsOn && predictions.parsed && submitterNames.length > 0 && (
              <span className="rounded bg-amber-500/20 px-1 text-[10px]">
                {effectiveSelectedSet.size}/{submitterNames.length}
              </span>
            )}
          </button>
        )}
        {source.source_url && (
          <a
            href={source.source_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto flex items-center gap-1 text-xs text-sky-300 hover:text-sky-200"
          >
            Source <ExternalLink className="h-3 w-3" />
          </a>
        )}
      </div>

      {predictionsOn && pane.tab === "graph" && (
        <PredictionsBar
          status={predictions.status}
          error={predictions.error}
          submitters={predictions.parsed?.submitters ?? []}
          selectedSet={effectiveSelectedSet}
          colorBySubmitter={colorBySubmitter}
          onToggleSubmitter={toggleSubmitter}
          onRetry={predictions.refetch}
          companionId={`EPI-Eval/${sourceIdSlug}-predictions`}
        />
      )}
      {predictionsOn && pane.tab === "graph" && scopeHint && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/[0.04] px-3 py-2 text-[11px] text-amber-200">
          Predictions are submitted against{" "}
          <span className="font-mono">{scopeHint.dimValue}</span>. The chart's
          truth slice is wider than that, so leaderboard metrics may not be
          apples-to-apples — apply a matching filter (e.g. set a categorical
          filter to <span className="font-mono">{scopeHint.dimValue}</span>) for
          aligned scoring.
        </div>
      )}
      {predictionsOn && pane.tab === "graph" && leaderboard.length > 0 && (
        <Leaderboard
          scores={leaderboard}
          selectedSet={effectiveSelectedSet}
          colorBySubmitter={colorBySubmitter}
          targetColumn={predictions.parsed?.targetColumn ?? null}
          targetColumnUnit={
            source?.value_columns.find(
              (c) => c.name === predictions.parsed?.targetColumn
            )?.unit ?? null
          }
        />
      )}

      {source.description && (
        <p className="text-xs leading-5 text-neutral-300">{source.description}</p>
      )}

      {slice.status === "loading" && (
        <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-5 py-6">
          <Loader2 className="h-6 w-6 shrink-0 animate-spin text-sky-400" aria-hidden="true" />
          <div>
            <p className="text-base font-semibold text-white">Fetching data from Huggingface…</p>
            <p className="text-xs text-neutral-400">Pulling rows for {source.pretty_name}.</p>
          </div>
        </div>
      )}
      {slice.status === "error" && (
        <div className="flex items-start justify-between gap-3 rounded-md border border-red-500/40 bg-red-950/20 px-3 py-2">
          <div className="text-sm text-red-200">
            <p className="font-semibold text-red-100">Failed to load.</p>
            <p className="mt-0.5 text-xs text-red-200/80">{slice.error}</p>
          </div>
          <button
            type="button"
            onClick={slice.refetch}
            className="flex shrink-0 items-center gap-1 rounded-md border border-red-300/50 bg-red-500/10 px-2.5 py-1 text-xs font-semibold text-red-100 transition hover:border-red-200 hover:bg-red-500/20"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        </div>
      )}

      {slice.status === "ready" && slice.data && (
        <>
          {pane.tab === "graph" ? (
            <SourceTimelineChart
              source={source}
              rows={slice.data.rows}
              metric={metric}
              onMetricChange={setMetric}
              activeFilters={activeFilters}
              onActiveFiltersChange={setActiveFilters}
              predictions={
                predictionsOn && predictions.parsed
                  ? {
                      parsed: predictions.parsed,
                      selectedSubmitters: effectiveSelectedSet,
                      colorBySubmitter
                    }
                  : undefined
              }
            />
          ) : (
            <DatasetMap source={source} rows={slice.data.rows} />
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-neutral-500">
            <span>
              {slice.data.truncated
                ? `Showing the first ${slice.data.rows.length.toLocaleString()} of ${slice.data.numRowsTotal.toLocaleString()} rows.`
                : `${slice.data.rows.length.toLocaleString()} rows.`}
            </span>
            <button
              type="button"
              onClick={() => setShowTable(!pane.showTable)}
              className="flex items-center gap-1 rounded border border-white/10 px-2 py-0.5 text-neutral-200 transition hover:border-sky-500 hover:text-sky-200"
            >
              <Table2 className="h-3 w-3" />
              {pane.showTable ? "Hide table" : "Show table"}
            </button>
          </div>

          {pane.showTable && <DataTable rows={slice.data.rows} filenameStem={source.id} />}
        </>
      )}
    </div>
  );
}

interface TabButtonProps {
  active: boolean;
  onClick: () => void;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  label: string;
}

interface LeaderboardProps {
  scores: SubmitterScore[];
  selectedSet: Set<string>;
  colorBySubmitter: Record<string, string>;
  targetColumn: string | null;
  targetColumnUnit: string | null;
}

function Leaderboard({
  scores,
  selectedSet,
  colorBySubmitter,
  targetColumn,
  targetColumnUnit
}: LeaderboardProps) {
  // Show selected submitters first, then unselected (greyed). Within
  // each group, rank by WIS asc (best first), null/zero-overlap rows last.
  const sortedScores = useMemo(() => {
    const score = (s: SubmitterScore) => (s.wis === null ? Infinity : s.wis);
    const selected = scores.filter((s) => selectedSet.has(s.submitter)).sort((a, b) => score(a) - score(b));
    const rest = scores.filter((s) => !selectedSet.has(s.submitter)).sort((a, b) => score(a) - score(b));
    return [...selected, ...rest];
  }, [scores, selectedSet]);

  const unit = targetColumnUnit ? ` ${targetColumnUnit}` : "";

  return (
    <div className="rounded-md border border-amber-500/20 bg-white/[0.02]">
      <div className="flex items-baseline justify-between border-b border-white/5 px-3 py-1.5">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-amber-200/80">
          Leaderboard
        </p>
        <p className="text-[10px] text-neutral-500">
          Scored vs <span className="font-mono text-neutral-300">{targetColumn}</span> · MAE/WIS
          {unit && <span className="text-neutral-600">, in{unit}</span>}; rWIS vs naive last-value (1 = baseline; lower is better)
        </p>
      </div>
      <div className="overflow-x-auto scrollbar-hidden">
        <table className="w-full min-w-max text-xs">
          <thead className="bg-white/[0.02] text-[10px] uppercase text-neutral-500">
            <tr>
              <th className="px-3 py-1.5 text-left font-semibold">Submitter</th>
              <th className="px-3 py-1.5 text-right font-semibold">N</th>
              <th className="px-3 py-1.5 text-right font-semibold">MAE</th>
              <th className="px-3 py-1.5 text-right font-semibold">WIS</th>
              <th className="px-3 py-1.5 text-right font-semibold">rWIS</th>
              <th className="px-3 py-1.5 text-right font-semibold">80% cov</th>
              <th className="px-3 py-1.5 text-right font-semibold">95% cov</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {sortedScores.map((s) => {
              const selected = selectedSet.has(s.submitter);
              const color = colorBySubmitter[s.submitter] ?? "#fbbf24";
              return (
                <tr key={s.submitter} className={selected ? "" : "opacity-50"}>
                  <td className="px-3 py-1.5">
                    <span className="flex items-center gap-1.5">
                      <span
                        aria-hidden="true"
                        className="inline-block h-2 w-2 shrink-0 rounded-sm"
                        style={{ background: color }}
                      />
                      <span className="font-mono text-neutral-100">{s.submitter}</span>
                      {s.isSynthetic && (
                        <span className="rounded bg-neutral-700/60 px-1 text-[9px] uppercase text-neutral-300">
                          synth
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-neutral-300">
                    {s.scoredCount}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-neutral-100">
                    {fmtNum(s.mae)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-neutral-100">
                    {fmtNum(s.wis)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono">
                    <span className={rwisToneClass(s.rWIS)}>{fmtNum(s.rWIS, 2)}</span>
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-neutral-200">
                    {fmtPct(s.coverage80)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-neutral-200">
                    {fmtPct(s.coverage95)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function fmtNum(v: number | null, digits = 1): string {
  if (v === null || !Number.isFinite(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function fmtPct(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

function rwisToneClass(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "text-neutral-300";
  if (v < 0.95) return "text-emerald-300";
  if (v > 1.05) return "text-rose-300";
  return "text-neutral-100";
}

interface PredictionsBarProps {
  status: "idle" | "loading" | "ready" | "error";
  error?: string;
  submitters: { submitter: string; rowCount: number; isSynthetic: boolean }[];
  selectedSet: Set<string>;
  colorBySubmitter: Record<string, string>;
  onToggleSubmitter: (submitter: string) => void;
  onRetry: () => void;
  companionId: string;
}

function PredictionsBar({
  status,
  error,
  submitters,
  selectedSet,
  colorBySubmitter,
  onToggleSubmitter,
  onRetry,
  companionId
}: PredictionsBarProps) {
  if (status === "loading") {
    return (
      <div className="flex items-center gap-2 rounded-md border border-amber-500/30 bg-amber-500/[0.04] px-3 py-2 text-[11px] text-amber-200">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading forecasts from <span className="font-mono">{companionId}</span>…
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="flex items-start justify-between gap-3 rounded-md border border-red-500/40 bg-red-950/20 px-3 py-2 text-xs text-red-200">
        <span>
          Couldn't load forecasts from <span className="font-mono">{companionId}</span>: {error}
        </span>
        <button
          type="button"
          onClick={onRetry}
          className="flex shrink-0 items-center gap-1 rounded border border-red-300/50 bg-red-500/10 px-2 py-0.5 text-[11px] font-semibold text-red-100 hover:border-red-200 hover:bg-red-500/20"
        >
          <RefreshCw className="h-3 w-3" />
          Retry
        </button>
      </div>
    );
  }
  if (submitters.length === 0) {
    return (
      <div className="rounded-md border border-amber-500/30 bg-amber-500/[0.04] px-3 py-2 text-[11px] text-amber-200">
        No forecasts have been submitted to{" "}
        <span className="font-mono">{companionId}</span> yet.
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-amber-500/20 bg-amber-500/[0.03] px-3 py-2 text-[11px]">
      <span className="mr-1 text-[10px] font-semibold uppercase text-amber-200/80">
        Forecasts
      </span>
      {submitters.map((s) => {
        const checked = selectedSet.has(s.submitter);
        const color = colorBySubmitter[s.submitter] ?? "#fbbf24";
        return (
          <button
            key={s.submitter}
            type="button"
            onClick={() => onToggleSubmitter(s.submitter)}
            aria-pressed={checked}
            title={`${s.rowCount} rows · ${
              s.isSynthetic ? "synthetic test data" : "submitted forecast"
            }`}
            className={`flex items-center gap-1.5 rounded-full border px-2 py-0.5 transition ${
              checked
                ? "border-white/20 bg-white/[0.06] text-neutral-100 hover:border-white/30"
                : "border-white/5 bg-transparent text-neutral-500 hover:text-neutral-300"
            }`}
          >
            <span
              aria-hidden="true"
              className="inline-block h-2 w-2 rounded-sm"
              style={{ background: color, opacity: checked ? 1 : 0.35 }}
            />
            <span>{s.submitter}</span>
            {s.isSynthetic && (
              <span className="rounded bg-neutral-700/60 px-1 text-[9px] uppercase text-neutral-300">
                synth
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

function TabButton({ active, onClick, icon: Icon, label }: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-semibold transition ${
        active ? "bg-sky-700/40 text-sky-100" : "text-neutral-300 hover:bg-white/[0.05] hover:text-white"
      }`}
      aria-pressed={active}
    >
      <Icon className="h-3.5 w-3.5" />
      <span>{label}</span>
    </button>
  );
}
