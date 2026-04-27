import { useEffect, useMemo, useState } from "react";
import { Info, Loader2, RefreshCw, Send, Table2 } from "lucide-react";
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
import { useDashboard } from "../../state/DashboardContext";
import { useWorkspace, type UserDatasetPane } from "../../state/WorkspaceContext";
import { usePredictions } from "../../state/PredictionsContext";
import { useDatasetSlice } from "../../data/hf/hooks";
import {
  detectCategoricalFields,
  detectDateField,
  type DatasetRow
} from "../../data/hf/rows";
import { pickAggregation } from "../../data/aggregation";
import { BUILTIN_PERIOD_KINDS, periodKindLabel } from "../../data/periods";
import { DataTable } from "../Graph/DataTable";
import { SeasonalChart } from "../Graph/SeasonalChart";
import {
  alignedPairs,
  meanAbsoluteError,
  meanAbsolutePercentageError,
  rootMeanSquaredError,
  signedBias,
  type JoinedPoint
} from "../../data/predictions/metrics";
import { validateDates, type DateValidation } from "../../data/predictions/validate";
import {
  buildQuantileForecasts,
  type QuantileForecastPoint
} from "../../data/predictions/quantile";
import {
  coverageRates,
  meanWIS,
  scoreForecasts,
  type CoverageStat
} from "../../data/predictions/wis";
import {
  BASELINE_LABELS,
  runBaseline,
  type BaselineKey,
  type TruthPoint
} from "../../data/predictions/baselines";
import type { UserDataset } from "../../data/predictions/types";
import type { SourceMetadata } from "../../types/source";
import { SubmitPredictionsDialog } from "./SubmitPredictionsDialog";

const TRUTH_COLOR = "#10b981"; // emerald-500
const PREDICTION_COLOR = "#f59e0b"; // amber-500
const BASELINE_COLOR = "#a3a3a3"; // neutral-400

// Same skip list as SourceTimelineChart's filter detection — these are
// row-level metadata (alt names, vintage timestamps) that aren't useful
// to filter on.
const ROW_LEVEL_NON_DIMS = ["location_id_native", "location_name", "as_of"];

const NOMINAL_BANDS = [
  { key: "interval95", width: 0.95, lowerQ: 0.025, upperQ: 0.975, opacity: 0.12 },
  { key: "interval80", width: 0.8, lowerQ: 0.1, upperQ: 0.9, opacity: 0.18 },
  { key: "interval50", width: 0.5, lowerQ: 0.25, upperQ: 0.75, opacity: 0.25 }
] as const;

interface Props {
  pane: UserDatasetPane;
}

export function UserDatasetBody({ pane }: Props) {
  const { catalog } = useDashboard();
  const { updatePane } = useWorkspace();
  const { getDataset } = usePredictions();
  const userDataset = getDataset(pane.userDatasetId);
  const [baselineKey, setBaselineKey] = useState<BaselineKey>("naive-last-value");
  const [submitOpen, setSubmitOpen] = useState(false);

  const setTarget = (targetSourceId: string | null, targetColumn: string | null) =>
    updatePane(pane.id, (p) =>
      p.type === "user-dataset" ? { ...p, targetSourceId, targetColumn } : p
    );
  const toggleTable = () =>
    updatePane(pane.id, (p) =>
      p.type === "user-dataset" ? { ...p, showTable: !p.showTable } : p
    );

  // Categorical pass-through columns from the prediction CSV. Computed at
  // the parent level so the submit button (in CompareHeader) can be wired
  // before the user has chosen a comparison target.
  const passthroughDimNames = useMemo(() => {
    if (!userDataset) return [] as string[];
    return detectCategoricalFields(userDataset.rows, [
      userDataset.dateField,
      ...userDataset.numericFields,
      ...(userDataset.quantileField ? [userDataset.quantileField] : [])
    ]).map((d) => d.name);
  }, [userDataset]);

  if (!userDataset) {
    return (
      <div className="space-y-2 p-4 text-sm">
        <p className="font-medium text-white">Prediction not found.</p>
        <p className="text-xs text-neutral-400">
          This pane references an uploaded dataset that no longer exists in
          local storage. Re-upload the CSV to bring it back.
        </p>
      </div>
    );
  }

  const target = pane.targetSourceId
    ? catalog.data?.find((s) => s.id === pane.targetSourceId) ?? null
    : null;
  const submitReady = Boolean(target && pane.targetColumn);

  return (
    <div className="space-y-3 p-3">
      <CompareHeader
        userDataset={userDataset}
        catalogReady={catalog.status === "ready"}
        sources={catalog.data ?? []}
        targetSourceId={pane.targetSourceId}
        targetColumn={pane.targetColumn}
        onChange={setTarget}
        submitReady={submitReady}
        onSubmit={() => setSubmitOpen(true)}
      />
      {target && pane.targetColumn ? (
        <ComparisonView
          userDataset={userDataset}
          target={target}
          targetColumn={pane.targetColumn}
          baselineKey={baselineKey}
          onChangeBaseline={setBaselineKey}
          showTable={pane.showTable}
          onToggleTable={toggleTable}
        />
      ) : (
        <ViewOnly
          userDataset={userDataset}
          showTable={pane.showTable}
          onToggleTable={toggleTable}
        />
      )}

      {submitOpen && target && pane.targetColumn && (
        <SubmitPredictionsDialog
          dataset={userDataset}
          targetDatasetId={target.id}
          targetColumn={pane.targetColumn}
          passthroughDims={passthroughDimNames}
          onClose={() => setSubmitOpen(false)}
        />
      )}
    </div>
  );
}

interface CompareHeaderProps {
  userDataset: UserDataset;
  catalogReady: boolean;
  sources: SourceMetadata[];
  targetSourceId: string | null;
  targetColumn: string | null;
  onChange: (sourceId: string | null, column: string | null) => void;
  submitReady: boolean;
  onSubmit: () => void;
}

function CompareHeader({
  userDataset,
  catalogReady,
  sources,
  targetSourceId,
  targetColumn,
  onChange,
  submitReady,
  onSubmit
}: CompareHeaderProps) {
  const target = targetSourceId
    ? sources.find((s) => s.id === targetSourceId) ?? null
    : null;
  const valueCols =
    target?.value_columns.filter((c) => c.dtype === "int" || c.dtype === "float") ?? [];

  return (
    <div className="flex flex-wrap items-end justify-between gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
      <div className="min-w-0 space-y-0.5">
        <p className="truncate text-sm font-semibold text-white" title={userDataset.filename}>
          {userDataset.filename}
        </p>
        <p className="text-[10px] text-neutral-500">
          {userDataset.rowCount.toLocaleString()} rows · {userDataset.numericFields.length}{" "}
          numeric column{userDataset.numericFields.length === 1 ? "" : "s"}
          {userDataset.quantileField && ` · quantile column "${userDataset.quantileField}"`}
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex flex-col gap-1 text-[10px] uppercase text-neutral-400">
          Compare to
          <select
            value={targetSourceId ?? ""}
            onChange={(e) => onChange(e.target.value || null, null)}
            disabled={!catalogReady}
            className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-xs text-white normal-case disabled:opacity-50"
          >
            <option value="">— View only —</option>
            {sources.map((s) => (
              <option key={s.id} value={s.id}>
                {s.pretty_name}
              </option>
            ))}
          </select>
        </label>
        {target && (
          <label className="flex flex-col gap-1 text-[10px] uppercase text-neutral-400">
            Target column
            <select
              value={targetColumn ?? ""}
              onChange={(e) => onChange(target.id, e.target.value || null)}
              className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-xs text-white normal-case"
            >
              <option value="">Pick a column…</option>
              {valueCols.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          onClick={submitReady ? onSubmit : undefined}
          disabled={!submitReady}
          title={
            submitReady
              ? `Open a community PR on EPI-Eval/${target?.id}-predictions`
              : "Pick a Compare to dataset and target column to enable submission"
          }
          className="flex h-[26px] items-center gap-1.5 self-end rounded-md border border-sky-500/40 bg-sky-500/10 px-2.5 text-[11px] font-semibold text-sky-100 transition hover:border-sky-400 hover:bg-sky-500/20 disabled:cursor-not-allowed disabled:border-white/10 disabled:bg-transparent disabled:text-neutral-500 disabled:hover:border-white/10 disabled:hover:bg-transparent"
        >
          <Send className="h-3 w-3" />
          Submit to HuggingFace
        </button>
      </div>
    </div>
  );
}

interface ViewOnlyProps {
  userDataset: UserDataset;
  showTable: boolean;
  onToggleTable: () => void;
}

function ViewOnly({ userDataset, showTable, onToggleTable }: ViewOnlyProps) {
  const valueField = userDataset.numericFields[0] ?? "value";
  const forecasts = useMemo(
    () =>
      buildQuantileForecasts(
        userDataset.rows,
        userDataset.dateField,
        valueField,
        userDataset.quantileField
      ),
    [userDataset, valueField]
  );

  const chartData = useMemo(
    () =>
      Array.from(forecasts.values())
        .map((fc) => buildChartRow(fc, null, null, fc.date))
        .sort((a, b) => a.date.localeCompare(b.date)),
    [forecasts]
  );
  const hasQuantiles = useMemo(() => availableBandsFromChart(chartData).length > 0, [chartData]);

  return (
    <>
      <div className="rounded-md border border-amber-500/30 bg-amber-500/[0.04] px-3 py-2 text-[11px] text-amber-200">
        View-only mode — pick a "Compare to" dataset above to score this
        forecast against truth (MAE / WIS / coverage / rWIS).
      </div>

      <div className="h-[360px] rounded-lg border border-white/10 bg-neutral-950 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="#262626" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: "#a3a3a3", fontSize: 12 }}
              stroke="#404040"
              minTickGap={28}
            />
            <YAxis tick={{ fill: "#a3a3a3", fontSize: 12 }} stroke="#404040" />
            <Tooltip content={<HoverCard />} cursor={{ stroke: "#525252", strokeWidth: 1 }} />
            {hasQuantiles && <Legend wrapperStyle={{ fontSize: 11, color: "#d4d4d8", paddingTop: 6 }} iconType="plainline" />}
            {NOMINAL_BANDS.map((b) => (
              <Area
                key={b.key}
                dataKey={b.key}
                name={`${Math.round(b.width * 100)}% interval`}
                stroke="none"
                fill={PREDICTION_COLOR}
                fillOpacity={b.opacity}
                isAnimationActive={false}
                connectNulls={false}
              />
            ))}
            <Line
              type="monotone"
              dataKey="point"
              name={hasQuantiles ? `${valueField} (median)` : valueField}
              stroke={PREDICTION_COLOR}
              strokeWidth={2.2}
              dot={false}
              activeDot={{ r: 4 }}
              connectNulls={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <TableSection
        rows={userDataset.rows}
        showTable={showTable}
        onToggleTable={onToggleTable}
        filenameStem={userDataset.filename.replace(/\.csv$/i, "") || userDataset.id}
      />
    </>
  );
}

interface ComparisonViewProps {
  userDataset: UserDataset;
  target: SourceMetadata;
  targetColumn: string;
  baselineKey: BaselineKey;
  onChangeBaseline: (k: BaselineKey) => void;
  showTable: boolean;
  onToggleTable: () => void;
}

function ComparisonView({
  userDataset,
  target,
  targetColumn,
  baselineKey,
  onChangeBaseline,
  showTable,
  onToggleTable
}: ComparisonViewProps) {
  const truthSlice = useDatasetSlice(target.id);
  const predValueField = userDataset.numericFields[0] ?? "value";

  // Categorical dims of the prediction (anything not date / numeric / quantile).
  const predictionDims = useMemo(
    () =>
      detectCategoricalFields(userDataset.rows, [
        userDataset.dateField,
        ...userDataset.numericFields,
        ...(userDataset.quantileField ? [userDataset.quantileField] : [])
      ]),
    [userDataset]
  );

  // Categorical dims of the truth (anything that's not the date / target
  // column / declared numeric / standard row-level metadata). The user
  // picks one value per dim that isn't also present in the prediction CSV.
  const truthDims = useMemo(() => {
    const rows = truthSlice.data?.rows ?? [];
    if (rows.length === 0) return [];
    const truthDateField = detectDateField(rows) ?? "";
    const declaredNumeric = target.value_columns
      .filter((c) => c.dtype === "int" || c.dtype === "float")
      .map((c) => c.name);
    return detectCategoricalFields(rows, [
      truthDateField,
      targetColumn,
      ...declaredNumeric,
      ...ROW_LEVEL_NON_DIMS
    ]);
  }, [truthSlice.data, target, targetColumn]);

  const predDimNames = useMemo(
    () => new Set(predictionDims.map((d) => d.name)),
    [predictionDims]
  );
  const missingDims = useMemo(
    () => truthDims.filter((d) => !predDimNames.has(d.name)),
    [truthDims, predDimNames]
  );

  const [dimPicks, setDimPicks] = useState<Record<string, string>>({});
  // Reset picks when the user switches target (different dim catalog).
  useEffect(() => {
    setDimPicks({});
  }, [target.id]);

  const allPicksSet =
    missingDims.length === 0 || missingDims.every((d) => Boolean(dimPicks[d.name]));

  const [chartMode, setChartMode] = useState<"time-series" | "seasonal">("time-series");
  const [periodKindIdx, setPeriodKindIdx] = useState(0);
  const periodKind = BUILTIN_PERIOD_KINDS[periodKindIdx];

  // Hoisted out of `computed` so the seasonal chart can reuse them without
  // recomputing.
  const userForecasts = useMemo(
    () =>
      buildQuantileForecasts(
        userDataset.rows,
        userDataset.dateField,
        predValueField,
        userDataset.quantileField
      ),
    [userDataset, predValueField]
  );

  const truthRows = truthSlice.data?.rows ?? [];
  const truthDateField = useMemo(() => detectDateField(truthRows), [truthRows]);
  const filteredTruthRows = useMemo(
    () => filterRowsByPicks(truthRows, dimPicks),
    [truthRows, dimPicks]
  );

  // Median rows for seasonal overlay — one (date, value) row per forecast
  // date using the user's point estimate (median).
  const predictionMedianRows = useMemo(() => {
    const out: DatasetRow[] = [];
    for (const fc of userForecasts.values()) {
      if (fc.point !== null) out.push({ date: fc.date, value: fc.point });
    }
    return out;
  }, [userForecasts]);

  const truthAggMethod = useMemo(
    () => pickAggregation(target.value_columns.find((c) => c.name === targetColumn)),
    [target, targetColumn]
  );

  const dateValidation = useMemo(
    () => validateDates(userDataset, target),
    [userDataset, target]
  );

  const computed = useMemo(() => {
    if (!allPicksSet) return null;
    if (!truthDateField || filteredTruthRows.length === 0) return null;

    const truthByDate = aggregateTruthByDate(filteredTruthRows, truthDateField, targetColumn);
    const truthPoints: TruthPoint[] = Array.from(truthByDate.entries()).map(([date, value]) => ({
      date,
      value
    }));

    const forecastDates = Array.from(userForecasts.keys());
    const baselinePreds = runBaseline(baselineKey, truthPoints, forecastDates);

    const userScored = scoreForecasts(userForecasts, truthByDate);
    const userMeanWISVal = meanWIS(userScored);
    const userCoverage = coverageRates(userScored);

    // Baseline as deterministic forecasts (no quantiles → WIS = MAE).
    const baselineForecasts = new Map<string, QuantileForecastPoint>();
    for (const [date, val] of baselinePreds) {
      baselineForecasts.set(date, { date, point: val, quantiles: new Map() });
    }
    const baselineScored = scoreForecasts(baselineForecasts, truthByDate);
    const baselineMeanWISVal = meanWIS(baselineScored);

    // Point-pair stats from joined point estimates.
    const allDates = new Set<string>([...userForecasts.keys(), ...truthByDate.keys()]);
    const userPointJoined: JoinedPoint[] = Array.from(allDates)
      .sort()
      .map((date) => ({
        date,
        predicted: userForecasts.get(date)?.point ?? null,
        observed: truthByDate.get(date) ?? null
      }));
    const aligned = alignedPairs(userPointJoined);
    const userMAE = meanAbsoluteError(aligned.predicted, aligned.observed);
    const userRMSE = rootMeanSquaredError(aligned.predicted, aligned.observed);
    const userBias = signedBias(aligned.predicted, aligned.observed);
    const userMAPE = meanAbsolutePercentageError(aligned.predicted, aligned.observed);

    const baselinePointJoined: JoinedPoint[] = Array.from(baselinePreds.entries()).map(
      ([date, predicted]) => ({
        date,
        predicted,
        observed: truthByDate.get(date) ?? null
      })
    );
    const baselineAligned = alignedPairs(baselinePointJoined);
    const baselineMAE = meanAbsoluteError(baselineAligned.predicted, baselineAligned.observed);

    const rWIS =
      userMeanWISVal !== null && baselineMeanWISVal !== null && baselineMeanWISVal > 0
        ? userMeanWISVal / baselineMeanWISVal
        : null;

    const chartData = Array.from(allDates)
      .sort()
      .map((date) =>
        buildChartRow(
          userForecasts.get(date) ?? null,
          truthByDate.get(date) ?? null,
          baselinePreds.get(date) ?? null,
          date
        )
      );

    return {
      chartData,
      userMAE,
      userRMSE,
      userBias,
      userMAPE,
      userMeanWIS: userMeanWISVal,
      userCoverage,
      baselineMAE,
      baselineMeanWIS: baselineMeanWISVal,
      rWIS,
      scoredCount: aligned.predicted.length
    };
  }, [
    filteredTruthRows,
    truthDateField,
    userForecasts,
    targetColumn,
    baselineKey,
    allPicksSet
  ]);

  const hasQuantiles =
    computed !== null && availableBandsFromChart(computed.chartData).length > 0;

  return (
    <>
      {predictionDims.length > 0 && (
        <div className="rounded-md border border-amber-500/30 bg-amber-500/[0.04] px-3 py-2 text-[11px] text-amber-200">
          Prediction has categorical column{predictionDims.length === 1 ? "" : "s"}{" "}
          {predictionDims.map((d) => `"${d.name}"`).join(", ")} — multi-dim joins
          aren't supported yet, so values are aggregated across dim
          combinations. (Multi-dim join is a v2 follow-up.)
        </div>
      )}
      {missingDims.length > 0 && (
        <DimPickers
          missing={missingDims}
          picks={dimPicks}
          onPick={(name, value) =>
            setDimPicks((prev) => ({ ...prev, [name]: value }))
          }
        />
      )}
      {missingDims.length > 0 && !allPicksSet && (
        <div className="rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs text-neutral-300">
          Pick a value for each truth dimension above to score the forecast.
        </div>
      )}

      <DateValidationBanner validation={dateValidation} />

      {truthSlice.status === "loading" && (
        <div className="flex items-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-5 py-6">
          <Loader2 className="h-6 w-6 shrink-0 animate-spin text-sky-400" aria-hidden="true" />
          <div>
            <p className="text-base font-semibold text-white">Fetching truth from Huggingface…</p>
            <p className="text-xs text-neutral-400">Pulling rows for {target.pretty_name}.</p>
          </div>
        </div>
      )}
      {truthSlice.status === "error" && (
        <div className="flex items-start justify-between gap-3 rounded-md border border-red-500/40 bg-red-950/20 px-3 py-2">
          <div className="text-sm text-red-200">
            <p className="font-semibold text-red-100">Failed to load truth.</p>
            <p className="mt-0.5 text-xs text-red-200/80">{truthSlice.error}</p>
          </div>
          <button
            type="button"
            onClick={truthSlice.refetch}
            className="flex shrink-0 items-center gap-1 rounded-md border border-red-300/50 bg-red-500/10 px-2.5 py-1 text-xs font-semibold text-red-100 transition hover:border-red-200 hover:bg-red-500/20"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        </div>
      )}

      {truthSlice.status === "ready" && computed && (
        <>
          {computed.scoredCount === 0 && (
            <div className="rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs text-neutral-300">
              No overlapping dates between the prediction and truth — metrics
              will populate once the prediction's dates land within the truth's
              coverage. (Forecast horizon and historical predictions both work.)
            </div>
          )}
          <MetricsRow
            mae={computed.userMAE}
            rmse={computed.userRMSE}
            bias={computed.userBias}
            mape={computed.userMAPE}
            wis={computed.userMeanWIS}
            rwis={computed.rWIS}
            scoredCount={computed.scoredCount}
            unit={inferUnit(target, targetColumn)}
            baselineKey={baselineKey}
          />
          {computed.userCoverage.length > 0 && <CoverageRow stats={computed.userCoverage} />}
          <BaselineControl
            baselineKey={baselineKey}
            onChange={onChangeBaseline}
            mae={computed.baselineMAE}
            wis={computed.baselineMeanWIS}
            rwisUndefined={
              computed.userMeanWIS !== null && computed.baselineMeanWIS === 0
            }
            unit={inferUnit(target, targetColumn)}
          />
          <ChartModeToggle
            chartMode={chartMode}
            onChangeMode={setChartMode}
            periodKindIdx={periodKindIdx}
            onChangePeriodKind={setPeriodKindIdx}
          />
          {chartMode === "time-series" ? (
            <ComparisonChart
              data={computed.chartData}
              predictedLabel={`${userDataset.filename} (${predValueField})`}
              observedLabel={`${target.pretty_name} (${targetColumn})`}
              baselineLabel={BASELINE_LABELS[baselineKey]}
              hasQuantiles={hasQuantiles}
            />
          ) : (
            <SeasonalChart
              rows={filteredTruthRows}
              dateField={truthDateField}
              metric={targetColumn}
              aggMethod={truthAggMethod}
              periodKind={periodKind}
              activeFilters={[]}
              overlay={{
                rows: predictionMedianRows,
                dateField: "date",
                valueField: "value",
                label: `${userDataset.filename} (median)`
              }}
            />
          )}
        </>
      )}

      <TableSection
        rows={userDataset.rows}
        showTable={showTable}
        onToggleTable={onToggleTable}
        filenameStem={userDataset.filename.replace(/\.csv$/i, "") || userDataset.id}
      />
    </>
  );
}

// ─── pure helpers ────────────────────────────────────────────────────────

function aggregateTruthByDate(
  rows: DatasetRow[],
  dateField: string,
  valueField: string
): Map<string, number> {
  const sums = new Map<string, { sum: number; count: number }>();
  for (const row of rows) {
    const dateRaw = row[dateField];
    const date =
      typeof dateRaw === "string"
        ? dateRaw.slice(0, 10)
        : String(dateRaw ?? "").slice(0, 10);
    if (!date) continue;
    const valRaw = row[valueField];
    const val = typeof valRaw === "number" ? valRaw : Number(valRaw);
    if (!Number.isFinite(val)) continue;
    const curr = sums.get(date);
    if (curr) {
      curr.sum += val;
      curr.count += 1;
    } else {
      sums.set(date, { sum: val, count: 1 });
    }
  }
  const out = new Map<string, number>();
  for (const [d, { sum, count }] of sums) out.set(d, sum / count);
  return out;
}

interface ChartRow {
  date: string;
  observed: number | null;
  point: number | null;
  baseline: number | null;
  interval50: [number, number] | null;
  interval80: [number, number] | null;
  interval95: [number, number] | null;
}

function buildChartRow(
  fc: QuantileForecastPoint | null,
  observed: number | null,
  baseline: number | null,
  date: string
): ChartRow {
  const make = (loQ: number, upQ: number): [number, number] | null => {
    if (!fc) return null;
    const lo = fc.quantiles.get(loQ);
    const up = fc.quantiles.get(upQ);
    if (lo === undefined || up === undefined) return null;
    return [lo, up];
  };
  return {
    date,
    observed,
    point: fc?.point ?? null,
    baseline,
    interval50: make(0.25, 0.75),
    interval80: make(0.1, 0.9),
    interval95: make(0.025, 0.975)
  };
}

function availableBandsFromChart(rows: ChartRow[]): string[] {
  const out = new Set<string>();
  for (const r of rows) {
    if (r.interval50) out.add("interval50");
    if (r.interval80) out.add("interval80");
    if (r.interval95) out.add("interval95");
  }
  return Array.from(out);
}

function inferUnit(target: SourceMetadata, column: string): string | null {
  return target.value_columns.find((c) => c.name === column)?.unit ?? null;
}

// ─── view fragments ──────────────────────────────────────────────────────

function DateValidationBanner({ validation }: { validation: DateValidation }) {
  if (validation.ok) return null;
  const total = validation.outOfRangeRows.length + validation.parseErrorRows.length;
  return (
    <div className="rounded-md border border-amber-500/40 bg-amber-500/[0.06] px-3 py-2 text-xs text-amber-100">
      <p className="font-semibold">
        {total} row{total === 1 ? "" : "s"} outside the truth dataset's coverage.
      </p>
      {validation.acceptedRange && (
        <p className="mt-1 text-[11px] text-amber-200/80">
          Accepted: {validation.acceptedRange.min} → {validation.acceptedRange.max} (truth
          coverage + ~2 months forecast horizon).
        </p>
      )}
      <p className="mt-1 text-[11px] text-amber-200/80">
        Out-of-range rows are kept on the chart but excluded from the metrics.
      </p>
    </div>
  );
}

interface MetricsRowProps {
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  mape: number | null;
  wis: number | null;
  rwis: number | null;
  scoredCount: number;
  unit: string | null;
  baselineKey: BaselineKey;
}

function MetricsRow({
  mae,
  rmse,
  bias,
  mape,
  wis,
  rwis,
  scoredCount,
  unit,
  baselineKey
}: MetricsRowProps) {
  return (
    <div className="flex flex-wrap gap-2 rounded-md border border-white/10 bg-white/[0.03] p-3 text-xs">
      <Stat
        label="MAE"
        value={mae}
        unit={unit}
        info="Mean Absolute Error — average of |predicted − observed|. Same units as the value. Lower is better."
      />
      <Stat
        label="RMSE"
        value={rmse}
        unit={unit}
        info="Root Mean Squared Error — sqrt of the mean of squared errors. Penalizes large errors more than MAE. Lower is better."
      />
      <Stat
        label="Bias"
        value={bias}
        unit={unit}
        info="Signed bias — mean of (predicted − observed). Positive = systematic over-prediction, negative = under. Zero means errors cancel out, not that the forecast is accurate."
      />
      <Stat
        label="MAPE"
        value={mape !== null ? mape * 100 : null}
        suffix="%"
        info="Mean Absolute Percentage Error — mean of |error| / |observed|. Useful for comparing across scales. Rows where observed = 0 are skipped."
      />
      {wis !== null && (
        <Stat
          label="WIS"
          value={wis}
          unit={unit}
          info="Weighted Interval Score (Bracher et al. 2021) — combines absolute median error with interval-width and miss penalties across all your quantile pairs. Reduces to MAE when there are no intervals. Same units as the value. Lower is better."
        />
      )}
      {rwis !== null && (
        <Stat
          label="rWIS"
          value={rwis}
          hint={`vs ${BASELINE_LABELS[baselineKey]}`}
          info="Relative WIS — your WIS divided by the baseline's WIS. <1 means you beat the baseline; >1 means the baseline is better. Pick the baseline below."
        />
      )}
      <Stat
        label="Scored"
        value={scoredCount}
        integer
        info="Number of dates with both an observed truth and a predicted point estimate. All metrics above are computed over these pairs."
      />
    </div>
  );
}

function CoverageRow({ stats }: { stats: CoverageStat[] }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-[11px] text-neutral-300">
      <span className="flex items-center gap-1 text-[10px] font-semibold uppercase text-neutral-400">
        Coverage
        <InfoBadge tip="Empirical coverage — fraction of scored dates where the truth fell inside the predicted interval. Compare to the nominal level (50% / 80% / 95%) to read calibration: close to nominal = well-calibrated, well above = over-cautious, well below = over-confident." />
      </span>
      {stats.map((c) => {
        const nominal = Math.round(c.intervalWidth * 100);
        const empirical = Math.round(c.empiricalRate * 100);
        const gap = Math.abs(empirical - nominal);
        const tone =
          gap <= 10
            ? "text-emerald-200"
            : gap <= 20
              ? "text-amber-200"
              : "text-red-200";
        return (
          <span key={c.intervalWidth}>
            {nominal}% nominal:{" "}
            <span className={`font-mono font-semibold ${tone}`}>{empirical}%</span>{" "}
            <span className="text-neutral-500">(n={c.count})</span>
          </span>
        );
      })}
    </div>
  );
}

interface BaselineControlProps {
  baselineKey: BaselineKey;
  onChange: (k: BaselineKey) => void;
  mae: number | null;
  wis: number | null;
  rwisUndefined: boolean;
  unit: string | null;
}

function BaselineControl({
  baselineKey,
  onChange,
  mae,
  wis,
  rwisUndefined,
  unit
}: BaselineControlProps) {
  const fmt = (v: number) => v.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-[11px] text-neutral-300">
      <label className="flex items-center gap-2">
        <span className="flex items-center gap-1 text-[10px] font-semibold uppercase text-neutral-400">
          Baseline
          <InfoBadge tip="Reference forecast used as the rWIS denominator. naive-last-value: most recent truth strictly before the target date. naive-last-week: truth from 7 days before (±3d). seasonal-naive: truth from ~1 year before (±7d). linear-trend: linear fit to the last 8 truth points, extrapolated to the target date." />
        </span>
        <select
          value={baselineKey}
          onChange={(e) => onChange(e.target.value as BaselineKey)}
          className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-xs text-white normal-case"
        >
          {(Object.keys(BASELINE_LABELS) as BaselineKey[]).map((k) => (
            <option key={k} value={k}>
              {BASELINE_LABELS[k]}
            </option>
          ))}
        </select>
      </label>
      {(mae !== null || wis !== null) && (
        <div className="flex items-baseline gap-3">
          {mae !== null && (
            <span>
              MAE <span className="font-mono font-semibold text-white">{fmt(mae)}</span>
              {unit && <span className="text-neutral-500"> {unit}</span>}
            </span>
          )}
          {wis !== null && (
            <span>
              WIS <span className="font-mono font-semibold text-white">{fmt(wis)}</span>
              {unit && <span className="text-neutral-500"> {unit}</span>}
            </span>
          )}
        </div>
      )}
      {rwisUndefined && (
        <span className="text-[10px] text-amber-300">
          Baseline WIS is 0 — rWIS is undefined for this comparison.
        </span>
      )}
    </div>
  );
}

interface DimPickersProps {
  missing: { name: string; values: string[] }[];
  picks: Record<string, string>;
  onPick: (name: string, value: string) => void;
}

interface ChartModeToggleProps {
  chartMode: "time-series" | "seasonal";
  onChangeMode: (m: "time-series" | "seasonal") => void;
  periodKindIdx: number;
  onChangePeriodKind: (i: number) => void;
}

function ChartModeToggle({
  chartMode,
  onChangeMode,
  periodKindIdx,
  onChangePeriodKind
}: ChartModeToggleProps) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <div className="inline-flex rounded-md border border-white/10 bg-white/[0.03] p-0.5">
        <button
          type="button"
          onClick={() => onChangeMode("time-series")}
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
          onClick={() => onChangeMode("seasonal")}
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
            onChange={(e) => onChangePeriodKind(Number(e.target.value))}
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
    </div>
  );
}

function DimPickers({ missing, picks, onPick }: DimPickersProps) {
  return (
    <div className="flex flex-wrap items-end gap-2 rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
      <span className="self-center text-[10px] font-semibold uppercase text-neutral-400">
        Filter truth by
      </span>
      {missing.map((dim) => (
        <label
          key={dim.name}
          className="flex flex-col gap-1 text-[10px] uppercase text-neutral-400"
        >
          {dim.name}
          <select
            value={picks[dim.name] ?? ""}
            onChange={(e) => onPick(dim.name, e.target.value)}
            className="rounded-md border border-white/10 bg-black/60 px-2 py-1 text-xs text-white normal-case"
          >
            <option value="">— pick —</option>
            {dim.values.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  );
}

function filterRowsByPicks(
  rows: DatasetRow[],
  picks: Record<string, string>
): DatasetRow[] {
  const keys = Object.keys(picks).filter((k) => Boolean(picks[k]));
  if (keys.length === 0) return rows;
  return rows.filter((r) => {
    for (const k of keys) {
      if (String(r[k] ?? "") !== picks[k]) return false;
    }
    return true;
  });
}

interface StatProps {
  label: string;
  value: number | null;
  unit?: string | null;
  suffix?: string;
  hint?: string;
  integer?: boolean;
  info?: string;
}

function Stat({ label, value, unit, suffix, hint, integer, info }: StatProps) {
  const display =
    value === null
      ? "—"
      : integer
        ? value.toLocaleString()
        : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return (
    <div className="flex min-w-[88px] flex-col rounded-md border border-white/5 bg-black/30 px-3 py-1.5">
      <span className="flex items-center gap-1 text-[10px] uppercase text-neutral-400">
        {label}
        {info && <InfoBadge tip={info} />}
      </span>
      <span className="mt-0.5 text-sm font-semibold text-white">
        {display}
        {suffix ?? ""}
      </span>
      {(unit || hint) && (
        <span className="text-[10px] text-neutral-500">{unit ?? hint}</span>
      )}
    </div>
  );
}

function InfoBadge({ tip }: { tip: string }) {
  return (
    <span className="group relative inline-flex items-center">
      <Info
        className="h-3 w-3 cursor-help text-neutral-500 group-hover:text-neutral-200"
        aria-label={tip}
      />
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute left-1/2 top-full z-50 mt-1.5 w-64 -translate-x-1/2 whitespace-normal rounded-md border border-white/15 bg-black/95 px-2.5 py-1.5 text-[11px] font-normal normal-case leading-snug tracking-normal text-neutral-200 opacity-0 shadow-lg backdrop-blur transition-opacity duration-150 group-hover:visible group-hover:opacity-100"
      >
        {tip}
      </span>
    </span>
  );
}

interface ComparisonChartProps {
  data: ChartRow[];
  predictedLabel: string;
  observedLabel: string;
  baselineLabel: string;
  hasQuantiles: boolean;
}

function ComparisonChart({
  data,
  predictedLabel,
  observedLabel,
  baselineLabel,
  hasQuantiles
}: ComparisonChartProps) {
  if (data.length === 0) {
    return (
      <div className="rounded-lg border border-white/10 bg-white/[0.03] p-4 text-sm text-neutral-300">
        No overlapping dates yet — pick a different target column or check the date format.
      </div>
    );
  }
  return (
    <div className="h-[400px] rounded-lg border border-white/10 bg-neutral-950 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 12, right: 18, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#262626" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "#a3a3a3", fontSize: 12 }}
            stroke="#404040"
            minTickGap={28}
          />
          <YAxis tick={{ fill: "#a3a3a3", fontSize: 12 }} stroke="#404040" />
          <Tooltip content={<HoverCard />} cursor={{ stroke: "#525252", strokeWidth: 1 }} />
          <Legend
            wrapperStyle={{ fontSize: 11, color: "#d4d4d8", paddingTop: 6 }}
            iconType="plainline"
          />
          {NOMINAL_BANDS.map((b) => (
            <Area
              key={b.key}
              dataKey={b.key}
              name={`${Math.round(b.width * 100)}% interval`}
              stroke="none"
              fill={PREDICTION_COLOR}
              fillOpacity={b.opacity}
              isAnimationActive={false}
              connectNulls={false}
            />
          ))}
          <Line
            type="monotone"
            dataKey="observed"
            name={observedLabel}
            stroke={TRUTH_COLOR}
            strokeWidth={2.2}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="point"
            name={hasQuantiles ? `${predictedLabel} (median)` : predictedLabel}
            stroke={PREDICTION_COLOR}
            strokeWidth={2.2}
            strokeDasharray="6 3"
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls={false}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="baseline"
            name={`Baseline: ${baselineLabel}`}
            stroke={BASELINE_COLOR}
            strokeWidth={1.5}
            strokeDasharray="2 4"
            dot={false}
            activeDot={{ r: 3 }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

interface TableSectionProps {
  rows: DatasetRow[];
  showTable: boolean;
  onToggleTable: () => void;
  filenameStem: string;
}

function TableSection({ rows, showTable, onToggleTable, filenameStem }: TableSectionProps) {
  return (
    <>
      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={onToggleTable}
          className="flex items-center gap-1 rounded border border-white/10 px-2 py-0.5 text-[11px] text-neutral-200 transition hover:border-sky-500 hover:text-sky-200"
        >
          <Table2 className="h-3 w-3" />
          {showTable ? "Hide table" : "Show table"}
        </button>
      </div>
      {showTable && <DataTable rows={rows} filenameStem={filenameStem} />}
    </>
  );
}

function HoverCard({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-white/10 bg-black/95 p-3 text-xs text-neutral-100 shadow-lg backdrop-blur">
      <p className="font-mono text-[10px] text-neutral-400">{String(label ?? "")}</p>
      <ul className="mt-1 space-y-0.5">
        {payload.map((p) => {
          const v = p.value;
          if (v === null || v === undefined) return null;
          const isRange = Array.isArray(v);
          const formatted = isRange
            ? `${formatNum(v[0])} – ${formatNum(v[1])}`
            : formatNum(v as number);
          return (
            <li key={String(p.dataKey)} className="flex items-center gap-2">
              <span
                aria-hidden="true"
                className="inline-block h-2 w-2 rounded-sm"
                style={{ background: p.color ?? "#0ea5e9" }}
              />
              <span className="text-neutral-200">{String(p.name)}:</span>
              <span className="font-mono text-neutral-100">{formatted}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function formatNum(v: unknown): string {
  if (typeof v === "number" && Number.isFinite(v))
    return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return String(v);
}
