import type { ReactNode } from "react";

interface SelectFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}

export function SelectField({ label, value, onChange, children }: SelectFieldProps) {
  return (
    <label className="block">
      <span className="mb-2 block text-xs font-semibold uppercase text-slate-400">{label}</span>
      <select
        className="w-full rounded-md border border-white/10 bg-ink-850 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-red-500"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </select>
    </label>
  );
}
