import { useState } from "react";
import { WorldMap } from "./WorldMap";
import type { SelectedCountry } from "../../types/dashboard";

export function MapPage() {
  const [selected, setSelected] = useState<SelectedCountry | null>(null);

  return (
    <div className="space-y-3">
      <header className="rounded-2xl border border-white/10 bg-black p-5">
        <p className="text-xs font-semibold uppercase text-red-300">Map</p>
        <h1 className="mt-1 text-2xl font-semibold">World view</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-400">
          {selected
            ? `Selected: ${selected.name} (${selected.iso3})`
            : "Click a country to select it. Higher-zoom granularity is available — scroll in for sub-country detail."}
        </p>
      </header>
      <div className="h-[calc(100vh-12rem)] min-h-[620px]">
        <WorldMap selectedCountry={selected} onCountrySelect={setSelected} />
      </div>
    </div>
  );
}
