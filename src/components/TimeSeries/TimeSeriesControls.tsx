import type { AvailableTimeSeriesOption, DateRangeState } from "../../types/timeseries";

interface TimeSeriesControlsProps {
  selectedCountryName: string;
  availableOptions: AvailableTimeSeriesOption[];
  sourceId: string | null;
  metric: string | null;
  dateRange: DateRangeState;
  onSourceChange: (sourceId: string) => void;
  onMetricChange: (metric: string) => void;
  onDateRangeChange: (range: DateRangeState) => void;
}

export function TimeSeriesControls({
  selectedCountryName,
  availableOptions,
  sourceId,
  metric,
  dateRange,
  onSourceChange,
  onMetricChange,
  onDateRangeChange
}: TimeSeriesControlsProps) {
  const sourceOptions = [...new Map(availableOptions.map((option) => [option.sourceId, option])).values()];
  const metrics = [
    ...new Set(availableOptions.filter((option) => !sourceId || option.sourceId === sourceId).map((option) => option.metric))
  ];
  const disabled = availableOptions.length === 0;

  return (
    <div className="grid gap-4 rounded-xl border border-white/10 bg-black p-4 text-white lg:grid-cols-4">
      <div>
        <p className="text-xs font-semibold uppercase text-neutral-500">Country</p>
        <p className="mt-2 rounded-md border border-white/10 bg-white/[0.04] px-3 py-2 text-sm">{selectedCountryName}</p>
      </div>
      <label className="grid gap-2 text-xs font-semibold uppercase text-neutral-500">
        Source
        <select
          className="rounded-md border border-white/10 bg-neutral-950 px-3 py-2 text-sm font-normal text-white disabled:cursor-not-allowed disabled:opacity-60"
          value={sourceId ?? ""}
          disabled={disabled}
          onChange={(event) => onSourceChange(event.target.value)}
        >
          <option value="">{disabled ? "No uploaded data" : "Select source"}</option>
          {sourceOptions.map((source) => (
            <option key={source.sourceId} value={source.sourceId}>
              {source.sourceName}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-2 text-xs font-semibold uppercase text-neutral-500">
        Metric
        <select
          className="rounded-md border border-white/10 bg-neutral-950 px-3 py-2 text-sm font-normal text-white disabled:cursor-not-allowed disabled:opacity-60"
          value={metric ?? ""}
          disabled={disabled || metrics.length === 0}
          onChange={(event) => onMetricChange(event.target.value)}
        >
          <option value="">{metrics.length === 0 ? "No uploaded metrics" : "Select metric"}</option>
          {metrics.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
      <label className="grid gap-2 text-xs font-semibold uppercase text-neutral-500">
        Date range
        <select
          className="rounded-md border border-white/10 bg-neutral-950 px-3 py-2 text-sm font-normal text-white"
          value={dateRange.preset}
          onChange={(event) => onDateRangeChange({ preset: event.target.value as DateRangeState["preset"] })}
        >
          <option value="14d">2 weeks</option>
          <option value="1m">1 month</option>
          <option value="3m">3 months</option>
          <option value="6m">6 months</option>
          <option value="1y">1 year</option>
          <option value="2y">2 years</option>
        </select>
      </label>
    </div>
  );
}
