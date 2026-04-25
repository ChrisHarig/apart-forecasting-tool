import { useState } from "react";
import type { AddSourceInput, SourceCategory, SourceValidationResult } from "../../types/source";
import { orderedSourceCategories, sourceCategoryLabels } from "../../data/sources/sourceCategories";

interface AddSourceModalProps {
  defaultCountryIso3: string | null;
  onClose: () => void;
  onSubmit: (input: AddSourceInput) => SourceValidationResult;
}

const initialInput: AddSourceInput = {
  name: "",
  url: "",
  category: "user_added",
  countries: [],
  dataType: "",
  updateCadence: "",
  notes: ""
};

export function AddSourceModal({ defaultCountryIso3, onClose, onSubmit }: AddSourceModalProps) {
  const [input, setInput] = useState<AddSourceInput>({
    ...initialInput,
    countries: defaultCountryIso3 ? [defaultCountryIso3] : []
  });
  const [validation, setValidation] = useState<SourceValidationResult | null>(null);

  const submit = () => {
    const result = onSubmit(input);
    setValidation(result);
    if (result.valid) onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/10 bg-white p-6 text-black shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase text-red-700">Local source registry</p>
            <h2 className="mt-1 text-2xl font-semibold">Add source</h2>
            <p className="mt-2 text-sm leading-6 text-neutral-600">
              User-added sources are stored in this browser only and are not validated. Add aggregate sources only.
            </p>
          </div>
          <button className="rounded-md border border-neutral-300 px-3 py-2 text-sm font-semibold hover:bg-neutral-100" type="button" onClick={onClose}>
            Close
          </button>
        </div>

        <div className="mt-5 grid gap-4">
          <label className="grid gap-2 text-sm font-semibold">
            Name
            <input className="rounded-md border border-neutral-300 px-3 py-2 font-normal" value={input.name} onChange={(event) => setInput({ ...input, name: event.target.value })} />
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            URL
            <input className="rounded-md border border-neutral-300 px-3 py-2 font-normal" value={input.url} onChange={(event) => setInput({ ...input, url: event.target.value })} />
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            Category
            <select
              className="rounded-md border border-neutral-300 px-3 py-2 font-normal"
              value={input.category}
              onChange={(event) => setInput({ ...input, category: event.target.value as SourceCategory })}
            >
              {orderedSourceCategories.map((category) => (
                <option key={category} value={category}>
                  {sourceCategoryLabels[category]}
                </option>
              ))}
            </select>
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            Countries covered
            <input
              className="rounded-md border border-neutral-300 px-3 py-2 font-normal"
              value={input.countries.join(", ")}
              placeholder="USA, CAN, GLOBAL"
              onChange={(event) =>
                setInput({
                  ...input,
                  countries: event.target.value
                    .split(",")
                    .map((item) => item.trim())
                    .filter(Boolean)
                })
              }
            />
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            Data type
            <input className="rounded-md border border-neutral-300 px-3 py-2 font-normal" value={input.dataType} onChange={(event) => setInput({ ...input, dataType: event.target.value })} />
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            Update cadence
            <input className="rounded-md border border-neutral-300 px-3 py-2 font-normal" value={input.updateCadence} onChange={(event) => setInput({ ...input, updateCadence: event.target.value })} />
          </label>
          <label className="grid gap-2 text-sm font-semibold">
            Notes
            <textarea className="min-h-24 rounded-md border border-neutral-300 px-3 py-2 font-normal" value={input.notes} onChange={(event) => setInput({ ...input, notes: event.target.value })} />
          </label>
        </div>

        {validation && (
          <div className="mt-4 space-y-2 text-sm">
            {validation.errors.map((error) => (
              <p key={error} className="rounded-md border border-red-200 bg-red-50 p-2 text-red-800">
                {error}
              </p>
            ))}
            {validation.warnings.map((warning) => (
              <p key={warning} className="rounded-md border border-neutral-200 bg-neutral-50 p-2 text-neutral-700">
                {warning}
              </p>
            ))}
          </div>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button className="rounded-md border border-neutral-300 px-4 py-2 text-sm font-semibold hover:bg-neutral-100" type="button" onClick={onClose}>
            Cancel
          </button>
          <button className="rounded-md bg-red-700 px-4 py-2 text-sm font-semibold text-white hover:bg-red-800" type="button" onClick={submit}>
            Save source
          </button>
        </div>
      </div>
    </div>
  );
}
