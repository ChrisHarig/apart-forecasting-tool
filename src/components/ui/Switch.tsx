interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}

export function Switch({ checked, onChange, label, description, disabled = false }: SwitchProps) {
  return (
    <label
      className={`flex items-start justify-between gap-3 rounded-md border border-white/10 bg-white/[0.03] p-3 transition ${
        disabled ? "cursor-not-allowed opacity-45" : "cursor-pointer hover:border-white/15 hover:bg-white/[0.05]"
      }`}
    >
      <span>
        <span className="block text-sm font-medium text-slate-100">{label}</span>
        {description && <span className="mt-1 block text-xs leading-5 text-slate-400">{description}</span>}
      </span>
      <input
        className="peer sr-only"
        type="checkbox"
        checked={checked}
        disabled={disabled}
        aria-label={label}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="mt-0.5 flex h-6 w-11 shrink-0 items-center rounded-full border border-white/10 bg-neutral-700 px-0.5 transition peer-checked:border-red-500/70 peer-checked:bg-red-700 peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-red-600">
        <span className={`h-5 w-5 rounded-full bg-white shadow transition ${checked ? "translate-x-5" : "translate-x-0"}`} />
      </span>
    </label>
  );
}
