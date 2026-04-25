interface SliderFieldProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  suffix?: string;
  disabled?: boolean;
}

export function SliderField({ label, value, min, max, step, onChange, suffix = "", disabled = false }: SliderFieldProps) {
  return (
    <label className={`block rounded-md border border-white/8 bg-white/[0.03] p-3 ${disabled ? "opacity-50" : ""}`}>
      <span className="flex items-center justify-between gap-3 text-sm font-medium text-slate-100">
        <span>{label}</span>
        <span className="font-mono text-xs text-red-300">
          {Number(value).toFixed(step < 1 ? 2 : 0)}
          {suffix}
        </span>
      </span>
      <input
        className="mt-3 h-2 w-full accent-red-600 disabled:accent-neutral-600"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
